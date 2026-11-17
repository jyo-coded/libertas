"""Adapters for ShadowNet's four site types. They're modelled on real engine types (a MyBB-style forum with RSS,
a marketplace, a ransomware leak blog with a JSON feed, and a paste site), and they follow the
cheapest-signal-first ladder: RSS/JSON/list pages for the pulse, then detail pages only for new items.

Item URLs are always rebuilt from the source's own base URL plus an ID. Links found in content are never
followed.
"""
from __future__ import annotations

import re
from email.utils import parsedate_to_datetime

from ...janus.sanitize import decode, parse_html, parse_json, parse_xml
from ..fetcher import FetchResult
from .base import Adapter, ItemContent, ItemRef, ParseDrift

DC = "{http://purl.org/dc/elements/1.1/}"
_ID = re.compile(r"^[A-Za-z0-9]{1,32}$")


def _safe_id(value) -> str:
    value = str(value or "").strip()
    if not _ID.match(value):
        raise ParseDrift(f"unexpected item id {value!r}")
    return value


def _text(el) -> str:
    return el.get_text("\n", strip=True) if el else ""


class ForumAdapter(Adapter):
    name, kind = "shadownet_forum", "forum"

    def pulse_url(self, base):
        return f"{base}/syndication.php"

    def parse_pulse(self, base, res: FetchResult):
        root = parse_xml(res.body)
        refs = []
        for item in root.findall("./channel/item"):
            tid = _safe_id((item.findtext("guid") or "").split("-")[-1])
            pub = item.findtext("pubDate")
            posted = parsedate_to_datetime(pub).isoformat(timespec="seconds") if pub else None
            refs.append(ItemRef(f"thread:{tid}", f"{base}/showthread.php?tid={tid}", "forum_thread",
                                (item.findtext("title") or "")[:300], (item.findtext(f"{DC}creator") or "")[:80],
                                posted, {"section": item.findtext("category") or ""}))
        return refs

    def parse_detail(self, base, ref, res):
        if res.status == 404:
            return None
        doc = parse_html(res.body, res.final_url, res.content_type, keep_soup=True)
        posts = doc.soup.select("div.post")
        if not posts:
            raise ParseDrift("thread page has no posts")
        first = posts[0]
        author_el = first.select_one(".post_author a")
        date_el = first.select_one(".post_date")
        replies = [{"author": _text(p.select_one(".post_author a")),
                    "text": _text(p.select_one(".post_body"))[:500]} for p in posts[1:]]
        return ItemContent(
            title=_text(doc.soup.select_one(".thread_title")) or ref.title,
            author=_text(author_el) or ref.author,
            body_text=_text(first.select_one(".post_body")),
            posted_at=date_el.get("data-ts") if date_el else ref.posted_at,
            extra={"section": ref.extra.get("section", ""), "replies": replies,
                   "signature": _text(first.select_one(".signature")),
                   "profile_path": author_el.get("href", "") if author_el else ""})


class MarketAdapter(Adapter):
    name, kind = "shadownet_market", "market"

    def pulse_url(self, base):
        return f"{base}/"

    def parse_pulse(self, base, res):
        doc = parse_html(res.body, res.final_url, res.content_type, keep_soup=True)
        refs = []
        for card in doc.soup.select("div.listing[data-id]"):
            lid = _safe_id(card.get("data-id"))
            t = card.select_one("time")
            refs.append(ItemRef(f"listing:{lid}", f"{base}/listing/{lid}", "market_listing",
                                _text(card.select_one(".ltitle"))[:300], _text(card.select_one(".vendor"))[:80],
                                t.get("datetime") if t else None))
        return refs

    def parse_detail(self, base, ref, res):
        if res.status == 404:
            return None
        doc = parse_html(res.body, res.final_url, res.content_type, keep_soup=True)
        title = doc.soup.select_one("h2.ltitle")
        if not title:
            raise ParseDrift("listing page has no title")
        facts = {}
        for row in doc.soup.select("table.grid tr"):
            th, td = row.select_one("th"), row.select_one("td")
            if th and td:
                facts[_text(th)] = _text(td)
        body = _text(doc.soup.select_one(".description"))
        body += "".join(f"\n{k}: {v}" for k, v in facts.items())
        t = doc.soup.select_one(".meta time")
        return ItemContent(_text(title), _text(doc.soup.select_one(".vendor")) or ref.author, body,
                           t.get("datetime") if t else ref.posted_at, {"facts": facts})


class LeakBlogAdapter(Adapter):
    name, kind = "shadownet_leakblog", "leakblog"
    pulse_is_complete = True

    def pulse_url(self, base):
        return f"{base}/api/victims.json"

    def parse_pulse(self, base, res):
        data = parse_json(res.body)
        refs = []
        for v in data.get("victims", []):
            vid = _safe_id(v.get("id"))
            refs.append(ItemRef(f"victim:{vid}", f"{base}/victim/{vid}", "leak_victim", str(v.get("name", ""))[:200],
                                str(data.get("group", ""))[:80], v.get("posted_at"),
                                {k: v.get(k) for k in ("country", "sector", "website", "deadline", "status", "data_size")}))
        return refs

    def parse_detail(self, base, ref, res):
        if res.status == 404:
            return None
        doc = parse_html(res.body, res.final_url, res.content_type, keep_soup=True)
        name = doc.soup.select_one("h2.vname")
        if not name:
            raise ParseDrift("victim page has no name")
        status = doc.soup.select_one("p[class^=status-]")
        body = "\n".join(x for x in (_text(doc.soup.select_one(".meta")), _text(status),
                                     _text(doc.soup.select_one(".description"))) if x)
        return ItemContent(_text(name), ref.author, body, ref.posted_at, dict(ref.extra))


class PasteAdapter(Adapter):
    name, kind = "shadownet_paste", "paste"

    def pulse_url(self, base):
        return f"{base}/"

    def parse_pulse(self, base, res):
        doc = parse_html(res.body, res.final_url, res.content_type, keep_soup=True)
        refs = []
        for row in doc.soup.select("tr.paste[data-id]"):
            pid = _safe_id(row.get("data-id"))
            t = row.select_one("time")
            refs.append(ItemRef(f"paste:{pid}", f"{base}/raw/{pid}", "paste", _text(row.select_one("a"))[:200],
                                _text(row.select_one(".author"))[:80], t.get("datetime") if t else None))
        return refs

    def parse_detail(self, base, ref, res):
        if res.status == 404:
            return None
        return ItemContent(ref.title, ref.author, decode(res.body, res.content_type)[:200_000], ref.posted_at, {})


ADAPTERS: dict[str, Adapter] = {a.name: a for a in (ForumAdapter(), MarketAdapter(), LeakBlogAdapter(), PasteAdapter())}
