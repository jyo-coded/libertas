"""Capture → item tracking → fast lane → alerts.

Evidence first: every fetch is recorded (with its quarantine hash) before anything is parsed. Items keep
first-seen / last-seen / deleted-at times, which give an "existence window" for court, and every content
change is kept as a version.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import timedelta

from .common.timeutil import now, now_iso, parse_iso, seconds_between
from .interpres.fastlane import assess
from .interpres.indicators import Extractor
from .interpres.watchlist import Watchlist
from .janus.quarantine import Quarantine
from .lex.audit import AuditLog
from .speculatores.adapters import ItemContent, ItemRef
from .speculatores.fetcher import FetchResult
from .vigiles.alerts import Vigiles
from .vigiles.bus import Bus

FRESH_WINDOW_S = 24 * 3600


class Pipeline:
    def __init__(self, conn: sqlite3.Connection, audit: AuditLog, quarantine: Quarantine, watchlist: Watchlist,
                 extractors: dict[bool, Extractor], vigiles: Vigiles, bus: Bus, log=print):
        self.conn, self.audit, self.quarantine = conn, audit, quarantine
        self.watchlist, self.extractors, self.vigiles, self.bus, self.log = watchlist, extractors, vigiles, bus, log
        self.deep = None  # DeepLane, attached after construction

    # ---------- evidence ----------
    def record_capture(self, source_id: str, res: FetchResult, role: str) -> str | None:
        sha = self.quarantine.put(res.body) if res.body is not None else None
        self.conn.execute(
            "INSERT INTO captures(source_id, url, final_url, fetched_at, status, content_type, bytes, sha256, elapsed_s, "
            "isolation_id, headers_json, outcome, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (source_id, res.url, res.final_url, now_iso(), res.status, res.content_type,
             len(res.body) if res.body is not None else 0, sha, res.elapsed_s, res.isolation_id,
             json.dumps({"headers": res.headers, "cookie_names": res.cookie_names, "role": role}), res.outcome,
             (res.refused or res.error)[:300]))
        return sha

    def record_descriptor(self, source_id: str, obs) -> None:
        self.conn.execute(
            "INSERT INTO descriptor_observations(source_id, onion, observed_at, result, seconds, hsdirs_asked, "
            "intro_points, pow_enabled, pow_effort, single_onion, private, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (source_id, obs.onion, now_iso(), obs.result, obs.seconds, obs.hsdirs_asked, obs.intro_points,
             obs.pow_enabled, obs.pow_effort, obs.single_onion, obs.private, obs.error))
        if obs.pow_effort:
            self.audit.append("pulsus", "under_load", source_id, "observed", {"pow_effort": obs.pow_effort})
        self.bus.publish({"type": "descriptor", "source_id": source_id, "observation": obs.as_dict()})

    # ---------- item tracking ----------
    def _item(self, source_id: str, key: str):
        return self.conn.execute("SELECT * FROM items WHERE source_id=? AND item_key=?", (source_id, key)).fetchone()

    def triage(self, source, refs: list[ItemRef], *, complete: bool) -> list[ItemRef]:
        """Record what the pulse saw. Returns refs whose detail page must be fetched now."""
        ts, need, seen = now_iso(), [], set()
        for ref in refs:
            seen.add(ref.key)
            row = self._item(source.id, ref.key)
            if row is None:
                self.conn.execute(
                    "INSERT INTO items(source_id, item_key, kind, url, title, author, posted_at, first_seen, last_seen, "
                    "extra_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (source.id, ref.key, ref.kind, ref.url, ref.title, ref.author, ref.posted_at, ts, ts,
                     json.dumps(ref.extra)))
                need.append(ref)
                continue
            self.conn.execute("UPDATE items SET last_seen=? WHERE id=?", (ts, row["id"]))
            old_extra = json.loads(row["extra_json"] or "{}")
            if row["deleted_at"] or row["content_hash"] is None:
                need.append(ref)
            elif ref.extra.get("status") and ref.extra.get("status") != old_extra.get("status"):
                self.conn.execute("UPDATE items SET extra_json=? WHERE id=?", (json.dumps({**old_extra, **ref.extra}), row["id"]))
                detail = {"from": old_extra.get("status")}
                if old_extra.get("deadline"):  # deadline-aware: how soon after the countdown ended did we see it
                    detail.update(deadline=old_extra["deadline"],
                                  seen_after_deadline_s=seconds_between(old_extra["deadline"], ts))
                self.audit.append("speculatores", "status_change", f"item:{row['id']}", ref.extra["status"], detail)
                self.bus.publish({"type": "status_change", "item_id": row["id"], **detail, "to": ref.extra["status"]})
                need.append(ref)
        if complete:
            for row in self.conn.execute("SELECT * FROM items WHERE source_id=? AND deleted_at IS NULL", (source.id,)).fetchall():
                if row["item_key"] not in seen:
                    self._gone(row, "removed from the listing (on a leak site this often means the victim paid)")
        return need

    def absence_suspects(self, source, refs: list[ItemRef]) -> list[ItemRef]:
        """For recency-ordered feeds (RSS, 'latest' pages): an item newer than the oldest one still listed should
        be in the feed. If it isn't, it was probably deleted, so verify it now instead of waiting for a revisit.
        This is only a hint. Deletion is confirmed only by the item's own page."""
        dated = [r.posted_at for r in refs if r.posted_at]
        if not dated:
            return []
        oldest = min(dated)
        keys = {r.key for r in refs}
        rows = self.conn.execute(
            "SELECT item_key, url, kind, title, author, posted_at FROM items WHERE source_id=? AND deleted_at IS NULL "
            "AND content_hash IS NOT NULL AND posted_at > ?", (source.id, oldest)).fetchall()
        return [ItemRef(r["item_key"], r["url"], r["kind"], r["title"] or "", r["author"] or "", r["posted_at"])
                for r in rows if r["item_key"] not in keys]

    def touch_checked(self, source_id: str, key: str) -> None:
        self.conn.execute("UPDATE items SET last_checked=? WHERE source_id=? AND item_key=?", (now_iso(), source_id, key))

    def on_content(self, source, ref: ItemRef, content: ItemContent, capture_sha: str | None) -> None:
        row = self._item(source.id, ref.key)
        ts = now_iso()
        digest = hashlib.sha256(f"{content.title}\n{content.body_text}".encode()).hexdigest()
        extra = {**json.loads(row["extra_json"] or "{}"), **ref.extra, **content.extra}
        posted = content.posted_at or ref.posted_at
        if row["content_hash"] is None or row["deleted_at"]:
            lag = seconds_between(posted, row["first_seen"])
            self.conn.execute(
                "UPDATE items SET title=?, author=?, body_text=?, posted_at=?, last_seen=?, last_checked=?, deleted_at=NULL, "
                "content_hash=?, first_capture_sha=COALESCE(first_capture_sha, ?), last_capture_sha=?, extra_json=?, "
                "detection_lag_s=? WHERE id=?",
                (content.title, content.author, content.body_text, posted, ts, ts, digest, capture_sha, capture_sha,
                 json.dumps(extra), lag, row["id"]))
            self._version(row["id"], ts, digest, capture_sha, content)
            fresh = lag is not None and lag <= FRESH_WINDOW_S
            self._assess(row["id"], fresh=fresh)
        elif digest != row["content_hash"]:
            self.conn.execute(
                "UPDATE items SET title=?, body_text=?, last_seen=?, last_checked=?, content_hash=?, last_capture_sha=?, "
                "extra_json=? WHERE id=?",
                (content.title, content.body_text, ts, ts, digest, capture_sha, json.dumps(extra), row["id"]))
            self._version(row["id"], ts, digest, capture_sha, content)
            self.audit.append("speculatores", "item_edited", f"item:{row['id']}", "changed", {"capture": capture_sha})
            self.bus.publish({"type": "item_edited", "item_id": row["id"]})
            self._assess(row["id"], fresh=self._recent(posted))
        else:
            self.conn.execute("UPDATE items SET last_seen=?, last_checked=?, last_capture_sha=? WHERE id=?",
                              (ts, ts, capture_sha, row["id"]))

    def mark_deleted(self, source, ref: ItemRef, capture_sha: str | None) -> None:
        row = self._item(source.id, ref.key)
        if row and not row["deleted_at"]:
            self._gone(row, "deleted at source (page now returns 'not found')", capture_sha)
        elif row:
            self.touch_checked(source.id, ref.key)

    def _gone(self, row: sqlite3.Row, how: str, capture_sha: str | None = None) -> None:
        ts = now_iso()
        lifetime = seconds_between(row["posted_at"] or row["first_seen"], ts)
        self.conn.execute("UPDATE items SET deleted_at=?, last_checked=? WHERE id=?", (ts, ts, row["id"]))
        self.audit.append("speculatores", "item_gone", f"item:{row['id']}", "recorded",
                          {"how": how, "lifetime_s": lifetime, "last_present": row["last_seen"],
                           "evidence_kept": row["first_capture_sha"], "absence_capture": capture_sha})
        self.vigiles.item_gone(row["id"], how, lifetime)
        self.log(f"item {row['id']} gone ({how}); lifetime {lifetime}s; evidence {row['first_capture_sha']}")

    def _version(self, item_id: int, ts: str, digest: str, sha: str | None, content: ItemContent) -> None:
        self.conn.execute("INSERT INTO item_versions(item_id, seen_at, content_hash, capture_sha, title, body_text) "
                          "VALUES (?,?,?,?,?,?)", (item_id, ts, digest, sha, content.title, content.body_text))

    @staticmethod
    def _recent(posted: str | None) -> bool:
        p = parse_iso(posted)
        return bool(p and now() - p <= timedelta(seconds=FRESH_WINDOW_S))

    # ---------- fast lane ----------
    def _assess(self, item_id: int, *, fresh: bool) -> None:
        item = self.conn.execute(
            "SELECT i.*, s.simulated FROM items i JOIN sources s ON s.id=i.source_id WHERE i.id=?", (item_id,)).fetchone()
        a = assess(item["title"] or "", item["body_text"] or "", kind=item["kind"],
                   extra=json.loads(item["extra_json"] or "{}"), posted_at=item["posted_at"], watchlist=self.watchlist,
                   extractor=self.extractors[bool(item["simulated"])])
        self.conn.execute("DELETE FROM indicators WHERE item_id=?", (item_id,))
        self.conn.executemany(
            "INSERT OR IGNORE INTO indicators(item_id, kind, value, display, valid, sensitive) VALUES (?,?,?,?,?,?)",
            [(item_id, i.kind, i.value, i.display, None if i.valid is None else int(i.valid), int(i.sensitive))
             for i in a.indicators])
        self.conn.execute(
            "INSERT OR REPLACE INTO assessments(item_id, assessed_at, method, categories_json, orgs_json, sectors_json, "
            "score, severity, factors_json, reasons_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (item_id, now_iso(), a.method, json.dumps(a.categories), json.dumps(a.orgs), json.dumps(a.sectors), a.score,
             a.severity, json.dumps({**a.factors, "stats": a.stats, "scale": a.scale}), json.dumps(a.reasons)))
        self.vigiles.upsert(item, a, fresh=fresh)
        self.bus.publish({"type": "item", "item_id": item_id, "severity": a.severity, "score": a.score})
        if self.deep:
            self.deep.submit(item_id)
