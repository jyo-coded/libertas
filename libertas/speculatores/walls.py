"""Walls: recognise the defences a site puts between the crawler and its content (blueprint 3.2, #61).

A wall is never solved, bypassed or argued with. It is recognised, recorded, and waited out: the source cools down,
moves to a fresh circuit, and tries again later. Recognising it matters because otherwise a CAPTCHA page looks like
a layout change and a rate-limit answer looks like an error to hammer through.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .fetcher import FetchResult

# Structural markers only. A post that merely talks about captchas is escaped text, so it can't match a form field.
_CAPTCHA_FIELD = re.compile(rb"<input[^>]+name=[\"'][^\"']*captcha", re.I)
# The whole title must be a challenge phrase: a thread *titled* "captcha solver for sale" is content, not a wall.
_WALL_TITLE = re.compile(rb"<title>\s*(security check|attention required!?|just a moment\.{0,3}|ddos-guard|"
                         rb"ddos protection by [^<]{1,40}|checking your browser[^<]{0,24}|verify you are human)\s*</title>",
                         re.I)
MIN_COOLDOWN_S, MAX_COOLDOWN_S, CAPTCHA_COOLDOWN_S = 10, 300, 60


@dataclass(frozen=True)
class Wall:
    kind: str  # "rate_limit" | "captcha" | "challenge"
    detail: str
    cooldown_s: int


def retry_after(res: FetchResult, default: int = 30) -> int:
    raw = (res.headers or {}).get("retry-after", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(MIN_COOLDOWN_S, min(MAX_COOLDOWN_S, value))


def detect_wall(res: FetchResult) -> Wall | None:
    if res.status == 429:
        wait = retry_after(res)
        return Wall("rate_limit", f"HTTP 429: the site asked us to wait {wait} s", wait)
    if not res.body or res.status not in (200, 403, 503):
        return None
    head = res.body[:65536]
    if _CAPTCHA_FIELD.search(head):
        return Wall("captcha", "CAPTCHA wall (never solved, by policy)", CAPTCHA_COOLDOWN_S)
    if _WALL_TITLE.search(head):
        return Wall("challenge", "anti-bot challenge page (never solved, by policy)", CAPTCHA_COOLDOWN_S)
    return None
