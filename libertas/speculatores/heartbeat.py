"""Heartbeat canary and deadline-aware polling (blueprint section 10 and #55).

Heartbeat: a canary onion publishes a new sequence number every minute together with the moment it was published.
The first time Libertas sees a new number, now minus 'published' is its true end-to-end time to detect, measured
continuously instead of only during demos.

Deadlines: ransomware leak sites show a countdown. Polling tightens as it runs out, so the publication moment is
caught within seconds and the victim can be warned before it.
"""
from __future__ import annotations

import re
import statistics
from collections import deque
from dataclasses import dataclass, field

from ..common.timeutil import now, parse_iso

_SEQ = re.compile(r"^seq:\s*(\d+)\s*$", re.M)
_PUBLISHED = re.compile(r"^published:\s*(\S+)\s*$", re.M)
STALE_AFTER_S = 150.0


def parse_canary(text: str) -> tuple[int, str] | None:
    if not text.startswith("LIBERTAS-CANARY"):
        return None
    seq, pub = _SEQ.search(text), _PUBLISHED.search(text)
    if not seq or not pub or not parse_iso(pub.group(1)):
        return None
    return int(seq.group(1)), pub.group(1)


@dataclass
class Heartbeat:
    onion: str = ""
    lags: deque = field(default_factory=lambda: deque(maxlen=60))
    last_seq: int | None = None
    last_new_at: float | None = None  # monotonic-free: epoch seconds
    consecutive_failures: int = 0
    checks: int = 0
    state: str = "starting"

    def observe(self, text: str, at_epoch: float) -> float | None:
        """Record one successful read. Returns the detection lag when a new minute was seen for the first time."""
        self.checks += 1
        self.consecutive_failures = 0
        parsed = parse_canary(text)
        if not parsed:
            self.state = "unreadable"
            return None
        seq, published = parsed
        lag = None
        if self.last_seq is not None and seq != self.last_seq:
            lag = round(at_epoch - parse_iso(published).timestamp(), 2)
            self.lags.append(lag)
        if seq != self.last_seq:
            self.last_seq, self.last_new_at = seq, at_epoch
        self.state = "ok"
        return lag

    def failed(self) -> None:
        self.checks += 1
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.state = "down"

    def refresh(self, at_epoch: float) -> None:
        if self.state == "ok" and self.last_new_at and at_epoch - self.last_new_at > STALE_AFTER_S:
            self.state = "stale"

    def summary(self) -> dict:
        lags = sorted(self.lags)
        return {"state": self.state, "onion": self.onion, "samples": len(lags), "checks": self.checks,
                "last_lag_s": self.lags[-1] if self.lags else None,
                "median_lag_s": round(statistics.median(lags), 1) if lags else None,
                "p95_lag_s": lags[min(len(lags) - 1, int(0.95 * len(lags)))] if lags else None,
                "recent_lags_s": list(self.lags)[-12:], "consecutive_failures": self.consecutive_failures}


def deadline_interval(remaining_s: float, base_s: float) -> float:
    """Pulse interval for a source with a countdown that has `remaining_s` seconds left (negative once it passed)."""
    if -180 <= remaining_s <= 120:
        return min(base_s, 5.0)
    if remaining_s <= 600:
        return min(base_s, 8.0)
    if remaining_s <= 3600:
        return min(base_s, 12.0)
    return base_s


def nearest_deadline(rows, at=None) -> dict | None:
    """rows: items (id, title, extra_json as dict) on a leak site. Returns the countdown that needs the tightest watch."""
    at = at or now()
    best = None
    for item_id, title, extra in rows:
        if (extra or {}).get("status") != "countdown":
            continue
        d = parse_iso(extra.get("deadline"))
        if not d:
            continue
        remaining = (d - at).total_seconds()
        if remaining < -180:
            continue
        if best is None or remaining < best["remaining_s"]:
            best = {"item_id": item_id, "title": title, "deadline": extra.get("deadline"), "remaining_s": round(remaining)}
    return best
