"""ShadowNet adversary mode (blueprint #61): the defences real criminal sites use, switchable from the panel, so the
crawler's resilience is tested rather than assumed.

  captcha     Kaal Forum thread and profile pages answer with a CAPTCHA wall instead of content
  ratelimit   every site answers HTTP 429 (Retry-After 20 s) once it sees more than 8 requests in 10 s
  randomise   Kaal Forum thread pages rename their CSS classes on every request (anti-scraper markup churn)
  fastdelete  any post created while this is on disappears 60 s after it was posted
  offline     DeadDrop's web server goes down behind its onion address (the service is unreachable)

The honeypot link hidden in Kaal Forum's footer is always armed. The heartbeat canary is a separate public onion
that changes every minute, so Libertas can measure its own end-to-end time to detect around the clock.
"""
from __future__ import annotations

import asyncio
import re
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from libertas.common.timeutil import now_iso

from .store import Store

MODES = {
    "captcha": "CAPTCHA wall on Kaal Forum thread and profile pages",
    "ratelimit": "Rate limit on every site: more than 8 requests in 10 s gets HTTP 429, Retry-After 20 s",
    "randomise": "Kaal Forum thread pages rename their CSS classes on every request",
    "fastdelete": "New posts on any site are deleted 60 s after posting",
    "offline": "DeadDrop's server goes down behind its onion address",
}
RATE_LIMIT, RATE_WINDOW_S, RETRY_AFTER_S = 8, 10.0, 20
FAST_DELETE_S = 60
FORUM_CLASSES = ("thread_title", "post_author", "post_body", "post_head", "post_date", "signature", "post")

CAPTCHA_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Security check</title></head>
<body style="background:#14161a;color:#d6d9de;font:14px Verdana,sans-serif;text-align:center;padding:60px">
<div style="background:#5c1a1a;color:#ffd7d7;padding:6px">SIMULATION (ShadowNet adversary mode)</div>
<h2>Security check</h2><p>Too many visitors. Prove you are human to continue.</p>
<form method="post" action="/captcha"><div style="font:28px monospace;letter-spacing:8px;margin:16px">{code}</div>
<input name="captcha_code" autocomplete="off"><input type="hidden" name="captcha_token" value="{token}">
<button>Continue</button></form></body></html>"""


class Adversary:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.on: dict[str, str | None] = {m: None for m in MODES}  # mode -> ISO time it was switched on
        self._hits: dict[str, deque] = {}
        self.counters = {"captcha_served": 0, "rate_limited": 0, "randomised": 0, "fast_deleted": 0,
                         "published_at_deadline": 0}
        self.on_offline_change = None  # set by the launcher: callable(bool)
        self.rate_limit = RATE_LIMIT  # requests per RATE_WINDOW_S before HTTP 429; drills can tighten it

    def active(self, mode: str) -> bool:
        return self.on.get(mode) is not None

    def set(self, mode: str, enabled: bool) -> None:
        if mode not in MODES:
            raise KeyError(mode)
        with self._lock:
            was = self.active(mode)
            self.on[mode] = (self.on[mode] or now_iso()) if enabled else None
        if mode == "offline" and was != enabled and self.on_offline_change:
            self.on_offline_change(enabled)

    def state(self) -> dict:
        return {"modes": {m: {"on": self.active(m), "since": self.on[m], "what": MODES[m]} for m in MODES},
                "counters": dict(self.counters)}

    def _rate_exceeded(self, site: str) -> bool:
        t = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(site, deque())
            while q and t - q[0] > RATE_WINDOW_S:
                q.popleft()
            q.append(t)
            return len(q) > self.rate_limit


def install(app: FastAPI, site_kind: str, adv: Adversary) -> None:
    """Wrap one site app with the switchable defences."""

    @app.middleware("http")
    async def defences(request: Request, call_next):
        path = request.url.path
        if adv.active("ratelimit") and adv._rate_exceeded(site_kind):
            adv.counters["rate_limited"] += 1
            return HTMLResponse("<!doctype html><title>429</title><h1>Too many requests</h1><p>Slow down.</p>",
                                status_code=429, headers={"Retry-After": str(RETRY_AFTER_S)})
        if site_kind == "forum" and adv.active("captcha") and path in ("/showthread.php", "/member.php"):
            adv.counters["captcha_served"] += 1
            code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
            return HTMLResponse(CAPTCHA_PAGE.format(code=code, token=secrets.token_hex(8)))
        response = await call_next(request)
        if site_kind == "forum" and adv.active("randomise") and path == "/showthread.php" and response.status_code == 200:
            body = b"".join([chunk async for chunk in response.body_iterator]).decode("utf-8")
            salt = secrets.token_hex(3)
            for cls in FORUM_CLASSES:  # exact attribute match, so "post" never touches "post_body"
                body = re.sub(rf'class="{cls}"', f'class="x{salt}{abs(hash(cls)) % 9999}"', body)
            adv.counters["randomised"] += 1
            headers = {k: v for k, v in response.headers.items() if k.lower() not in ("content-length",)}
            return Response(body, status_code=200, headers=headers, media_type="text/html")
        return response


async def scheduler(store: Store, adv: Adversary, log=print) -> None:
    """Background jobs: 60-second deletions while fastdelete is on, and ransomware deadlines that publish on time."""
    while True:
        await asyncio.sleep(2)
        try:
            since = adv.on.get("fastdelete")
            if since:
                cutoff = (datetime.now(timezone.utc) - timedelta(seconds=FAST_DELETE_S)).isoformat(timespec="seconds")
                for kind, key in store.created_between(since[:19] + "+00:00", cutoff):
                    store.delete_any(kind, key)
                    adv.counters["fast_deleted"] += 1
                    log(f"adversary: {kind} {key} deleted {FAST_DELETE_S} s after posting")
            for vid in store.publish_due_victims(datetime.now(timezone.utc).isoformat(timespec="seconds")):
                adv.counters["published_at_deadline"] += 1
                log(f"ShadowLock: deadline passed, victim {vid} data published")
        except Exception as exc:  # the demo world must keep running
            log(f"adversary scheduler error: {exc!r}")


def heartbeat_app() -> FastAPI:
    """The canary page. Its sequence number changes on every UTC minute, and it says when that minute began, so
    the first time Libertas sees a new number it can work out exactly how long detection took."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/")
    def canary():
        t = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        seq = int(t.timestamp() // 60)
        return PlainTextResponse(f"LIBERTAS-CANARY\nseq: {seq}\npublished: {t.isoformat()}\n"
                                 "note: heartbeat page for measuring end-to-end time to detect (simulation)\n")

    return app
