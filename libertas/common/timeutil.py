from __future__ import annotations

from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat(timespec="milliseconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


IST = timezone(timedelta(hours=5, minutes=30), "IST")


def to_ist(value: str | None, with_seconds: bool = True) -> str:
    """'2026-11-17T18:16:40+00:00' -> '17/11/2026 23:46:40 IST' (the format Indian courts expect)."""
    dt = parse_iso(value)
    if not dt:
        return "—"
    return dt.astimezone(IST).strftime("%d/%m/%Y %H:%M:%S IST" if with_seconds else "%d/%m/%Y %H:%M IST")


def seconds_between(earlier: str | None, later: str | None) -> float | None:
    a, b = parse_iso(earlier), parse_iso(later)
    if not a or not b:
        return None
    return round((b - a).total_seconds(), 2)
