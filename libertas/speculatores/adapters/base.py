"""Site adapters turn safely-parsed pages into items. They never follow links off the source's own host."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..fetcher import FetchResult


class ParseDrift(Exception):
    """The page no longer looks like the adapter expects (layout change). Raised, logged, never guessed past."""


@dataclass
class ItemRef:
    key: str
    url: str
    kind: str
    title: str = ""
    author: str = ""
    posted_at: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class ItemContent:
    title: str
    author: str
    body_text: str
    posted_at: str | None
    extra: dict = field(default_factory=dict)


class Adapter:
    name = "base"
    kind = ""
    # True when the pulse lists every live item, so an item missing from it has been removed
    pulse_is_complete = False

    def pulse_url(self, base: str) -> str:
        raise NotImplementedError

    def parse_pulse(self, base: str, res: FetchResult) -> list[ItemRef]:
        raise NotImplementedError

    def parse_detail(self, base: str, ref: ItemRef, res: FetchResult) -> ItemContent | None:
        """Return None when the item no longer exists (deleted / removed)."""
        raise NotImplementedError
