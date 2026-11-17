"""Zero-execution HTTP fetcher over Tor (blueprint §11.3 tier T1, §11.14).

A WatchSession is one source's isolated Tor circuit (unique SOCKS credentials, which Tor isolates by default)
with a small keep-alive pool, so repeated polls reuse the expensive rendezvous circuit (≈0.5 s vs ≈5 s, §3.3).

It returns bytes and metadata only. It never interprets, renders or executes what it fetches, it accepts only
text-like content types, it decompresses under a hard cap, and every request and redirect hop passes Lex.
"""
from __future__ import annotations

import secrets
import time
import zlib
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx

from ..config import Settings
from ..lex.policy import Lex

ALLOWED_CONTENT_TYPES = frozenset({
    "text/html", "application/xhtml+xml", "text/plain", "application/json",
    "application/xml", "text/xml", "application/rss+xml", "application/atom+xml",
})
KEPT_HEADERS = ("content-type", "content-length", "content-encoding", "server", "date", "last-modified",
                "etag", "cache-control", "x-powered-by", "location")


class Refused(Exception):
    """Raised internally when a response breaks a zero-execution or resource rule."""


@dataclass
class FetchResult:
    url: str
    final_url: str
    isolation_id: str
    status: int = 0
    content_type: str = ""
    body: bytes | None = None
    elapsed_s: float = 0.0
    headers: dict = field(default_factory=dict)
    cookie_names: list[str] = field(default_factory=list)
    refused: str = ""
    error: str = ""
    not_modified: bool = False

    @property
    def ok(self) -> bool:
        return not self.refused and not self.error and self.status == 200 and self.body is not None

    @property
    def outcome(self) -> str:
        if self.refused:
            return "refused"
        if self.error:
            return "error"
        if self.not_modified:
            return "not_modified"
        return f"http_{self.status}"


def browser_headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i",
    }


def decompress_capped(data: bytes, encoding: str, limit: int) -> bytes:
    """Decompress ourselves with a hard output cap (decompression-bomb guard)."""
    enc = (encoding or "identity").strip().lower()
    if enc in ("identity", ""):
        if len(data) > limit:
            raise Refused("response exceeds size cap")
        return data
    if enc in ("gzip", "x-gzip"):
        candidates = [16 + zlib.MAX_WBITS]
    elif enc == "deflate":
        candidates = [zlib.MAX_WBITS, -zlib.MAX_WBITS]
    else:
        raise Refused(f"content-encoding '{enc}' not accepted")
    last_error = None
    for wbits in candidates:
        decoder = zlib.decompressobj(wbits)
        try:
            out = decoder.decompress(data, limit + 1)
        except zlib.error as exc:
            last_error = exc
            continue
        if len(out) > limit or decoder.unconsumed_tail:
            raise Refused("decompressed body exceeds cap (possible decompression bomb)")
        return out
    raise Refused(f"undecodable {enc} body: {last_error}")


class WatchSession:
    def __init__(self, source_id: str, settings: Settings, lex: Lex, *,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.source_id = source_id
        self.settings = settings
        self.lex = lex
        self._transport = transport
        self._validators: dict[str, dict[str, str]] = {}
        self.requests = 0
        self._client = self._new_client()

    def _new_client(self) -> httpx.AsyncClient:
        self.isolation_id = secrets.token_hex(8)
        kwargs: dict = dict(
            headers=browser_headers(self.settings),
            timeout=httpx.Timeout(self.settings.request_timeout_s, connect=self.settings.connect_timeout_s),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2, keepalive_expiry=600),
        )
        if self._transport is not None:
            kwargs["transport"] = self._transport
        else:
            kwargs["proxy"] = (f"socks5://{self.isolation_id}:libertas@"
                               f"{self.settings.socks_host}:{self.settings.socks_port}")
        return httpx.AsyncClient(**kwargs)

    async def rotate(self) -> None:
        """Move this source to a fresh, isolated circuit (used after ban signals)."""
        old = self._client
        self._client = self._new_client()
        await old.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, url: str, *, conditional: bool = False) -> FetchResult:
        started = time.perf_counter()
        current = url

        def result(**kw) -> FetchResult:
            return FetchResult(url=url, final_url=current, isolation_id=self.isolation_id,
                               elapsed_s=round(time.perf_counter() - started, 3), **kw)

        for _hop in range(self.settings.max_redirects + 1):
            decision = self.lex.check_fetch("GET", current, source_id=self.source_id)
            if not decision.allowed:
                return result(refused=decision.reason)
            extra = dict(self._validators.get(current, {})) if conditional else {}
            try:
                async with self._client.stream("GET", current, headers=extra) as resp:
                    self.requests += 1
                    status = resp.status_code
                    kept = {k: resp.headers[k] for k in KEPT_HEADERS if k in resp.headers}
                    cookies = [c.split("=", 1)[0].strip()[:60] for c in resp.headers.get_list("set-cookie")]
                    if status in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            return result(status=status, headers=kept, refused="redirect without location")
                        current = urljoin(current, location)
                        continue
                    if status == 304:
                        return result(status=304, headers=kept, not_modified=True)
                    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ctype not in ALLOWED_CONTENT_TYPES:
                        return result(status=status, content_type=ctype, headers=kept,
                                      refused=f"content-type '{ctype or 'missing'}' refused: text and metadata only")
                    declared = resp.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > self.settings.max_compressed_bytes:
                        return result(status=status, content_type=ctype, headers=kept,
                                      refused="declared size exceeds cap")
                    raw = bytearray()
                    if resp.is_stream_consumed:  # body already in memory (some transports pre-read)
                        raw.extend(resp.content)
                    else:
                        async for chunk in resp.aiter_raw():
                            raw.extend(chunk)
                            if len(raw) > self.settings.max_compressed_bytes:
                                break
                    if len(raw) > self.settings.max_compressed_bytes:
                        return result(status=status, content_type=ctype, headers=kept,
                                      refused="response exceeds size cap")
                    body = decompress_capped(bytes(raw), resp.headers.get("content-encoding", ""),
                                             self.settings.max_response_bytes)
                    validators = {}
                    if "etag" in resp.headers:
                        validators["If-None-Match"] = resp.headers["etag"]
                    if "last-modified" in resp.headers:
                        validators["If-Modified-Since"] = resp.headers["last-modified"]
                    if validators:
                        self._validators[current] = validators
                    return result(status=status, content_type=ctype, body=body, headers=kept, cookie_names=cookies)
            except Refused as exc:
                return result(refused=str(exc))
            except (httpx.HTTPError, OSError) as exc:
                return result(error=f"{type(exc).__name__}: {exc}"[:300])
        return result(refused="too many redirects")
