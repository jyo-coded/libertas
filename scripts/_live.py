"""Shared helpers for the rehearsal and drill scripts: talk to a running Libertas and ShadowNet on localhost."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "http://127.0.0.1:8700"
PANEL = "http://127.0.0.1:8600"
ROOT = Path(__file__).resolve().parent.parent
VAR = ROOT / "var"
CLIENT = {"X-Libertas-Client": "forum"}  # Libertas refuses writes without it (CSRF guard)


def _req(url: str, method: str = "GET", headers: dict | None = None, timeout: float = 60, data: bytes | None = None):
    if method == "POST" and data is None:
        data = b""
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get(path: str):
    return json.loads(_req(API + path))


def post(path: str, body: dict | None = None):
    headers = dict(CLIENT)
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    return json.loads(_req(API + path, "POST", headers, timeout=120, data=data))


def download(path: str) -> bytes:
    return _req(API + path, timeout=120)


def panel(path: str):
    """ShadowNet's local control panel JSON API."""
    return json.loads(_req(PANEL + path, "POST"))


def panel_get(path: str):
    return json.loads(_req(PANEL + path))


def panel_form(path: str) -> None:
    """Panel form endpoints answer with a 303 redirect; that is success."""
    try:
        _req(PANEL + path, "POST")
    except urllib.error.HTTPError as exc:
        if exc.code not in (302, 303):
            raise


def wait(check, timeout: float, every: float = 1.0):
    """Poll `check()` until it returns something truthy; returns (value, seconds) or (None, timeout)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            value = check()
        except (urllib.error.URLError, OSError, ValueError):
            value = None
        if value:
            return value, round(time.monotonic() - t0, 1)
        time.sleep(every)
    return None, round(timeout, 1)


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(folder: str, record: dict) -> Path:
    d = VAR / folder
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def sources_in(state_test) -> dict | None:
    st = get("/api/status")
    srcs = st["sources"]
    return st if srcs and all(state_test(s.get("health", {}).get("state") or "") for s in srcs) else None


def audit_since(seq: int, action: str | None = None) -> list[dict]:
    rows = [r for r in get("/api/audit/tail?limit=200") if r["seq"] > seq]
    return [r for r in rows if action is None or r["action"] == action]


def audit_head() -> int:
    tail = get("/api/audit/tail?limit=1")
    return tail[0]["seq"] if tail else 0


def table(rows: list[tuple], headers: tuple) -> str:
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
    line = lambda r: "  ".join(str(x).ljust(w) for x, w in zip(r, widths))  # noqa: E731
    return "\n".join([line(headers), line(tuple("-" * w for w in widths))] + [line(r) for r in rows])
