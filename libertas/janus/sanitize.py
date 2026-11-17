"""Turn hostile bytes into inert text and metadata. Nothing here executes anything.

* HTML: Python's pure html.parser via BeautifulSoup; dangerous elements removed before text extraction;
  event-handler attributes and script URLs dropped; links and images kept as metadata only.
* XML/RSS: defusedxml (blocks entity-expansion and external-entity attacks).
* JSON: size-capped json.loads.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment
from defusedxml import ElementTree as SafeET

from ..lex.policy import BLOCKED_EXTENSIONS

DANGEROUS_TAGS = [
    "script", "style", "noscript", "iframe", "frame", "frameset", "object", "embed", "applet", "template",
    "svg", "math", "canvas", "video", "audio", "source", "track", "link", "base", "portal",
]
_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)"
    r"|left\s*:\s*-\d{3,}px|top\s*:\s*-\d{3,}px|width\s*:\s*0(?:px)?\s*;.*height\s*:\s*0", re.I)
_HIDDEN_CLASS = re.compile(r"\b(hidden|hide|invisible|sr-only|visually-hidden|d-none)\b", re.I)
MAX_TEXT_CHARS = 200_000


@dataclass
class Link:
    url: str
    text: str
    hidden: bool
    is_file: bool
    ext: str


@dataclass
class SafeDoc:
    title: str
    text: str
    links: list[Link] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    forms: int = 0
    removed_elements: int = 0
    soup: BeautifulSoup | None = None


def decode(raw: bytes, content_type: str = "") -> str:
    charset = ""
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    for enc in [c for c in (charset, "utf-8") if c]:
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("cp1252", errors="replace")


def _is_hidden(el) -> bool:
    node, depth = el, 0
    while node is not None and getattr(node, "name", None) and depth < 6:
        attrs = getattr(node, "attrs", {}) or {}
        if "hidden" in attrs or str(attrs.get("aria-hidden", "")).lower() == "true":
            return True
        if _HIDDEN_STYLE.search(str(attrs.get("style", ""))):
            return True
        cls = attrs.get("class", [])
        if _HIDDEN_CLASS.search(" ".join(cls) if isinstance(cls, list) else str(cls)):
            return True
        node, depth = node.parent, depth + 1
    return False


def _ext(url: str) -> str:
    try:
        return PurePosixPath(urlsplit(url).path).suffix.lower()
    except ValueError:
        return ""


def parse_html(raw: bytes, base_url: str, content_type: str = "", *, keep_soup: bool = False) -> SafeDoc:
    soup = BeautifulSoup(decode(raw, content_type), "html.parser")
    title = soup.title.get_text(" ", strip=True)[:300] if soup.title else ""
    meta = {}
    for m in soup.find_all("meta"):
        key = m.get("name") or m.get("property")
        if key:
            meta[str(key)[:60]] = str(m.get("content", ""))[:300]
    removed = 0
    for tag in soup.find_all(DANGEROUS_TAGS):
        tag.decompose()
        removed += 1
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for el in soup.find_all(True):
        for attr in list(el.attrs):
            value = str(el.attrs.get(attr, ""))
            if attr.lower().startswith("on") or value.strip().lower().startswith(("javascript:", "vbscript:")):
                del el.attrs[attr]
    links: list[Link] = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.lower().startswith(("javascript:", "data:", "vbscript:", "mailto:")):
            continue
        url = urljoin(base_url, href)
        ext = _ext(url)
        links.append(Link(url, a.get_text(" ", strip=True)[:200], _is_hidden(a), ext in BLOCKED_EXTENSIONS, ext))
    images = []
    for img in soup.find_all("img"):
        src = str(img.get("src", "")).strip()
        if src and not src.lower().startswith("data:"):
            images.append(urljoin(base_url, src))
    forms = len(soup.find_all("form"))
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)[:MAX_TEXT_CHARS]
    return SafeDoc(title, text, links, images, meta, forms, removed, soup if keep_soup else None)


def parse_xml(raw: bytes):
    """Parse XML/RSS/Atom safely. Raises defusedxml exceptions on entity tricks."""
    return SafeET.fromstring(raw, forbid_dtd=True)


def parse_json(raw: bytes, limit: int = 2_000_000):
    if len(raw) > limit:
        raise ValueError("JSON too large")
    return json.loads(decode(raw))
