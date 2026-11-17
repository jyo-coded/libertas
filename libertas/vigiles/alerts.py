"""Vigiles: alerts and escalation (blueprint #30, #31).

Fresh items (posted in the last 24 h before first sight) raise live alerts. Items found during a backfill of
older content are recorded as 'historical', so the first sweep of a source never floods the duty officer.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3

import httpx

from ..common.timeutil import now_iso
from ..config import Settings
from ..interpres.fastlane import Assessment
from ..interpres.india import mask_pii
from ..lex.audit import AuditLog
from .bus import Bus

PUSH_SEVERITIES = {"CRITICAL", "HIGH"}


class Vigiles:
    def __init__(self, conn: sqlite3.Connection, audit: AuditLog, bus: Bus, settings: Settings, log=print):
        self.conn, self.audit, self.bus, self.settings, self.log = conn, audit, bus, settings, log

    def upsert(self, item: sqlite3.Row, a: Assessment, *, fresh: bool) -> dict | None:
        existing = self.conn.execute("SELECT id, severity, status FROM alerts WHERE item_id=?", (item["id"],)).fetchone()
        if a.score < self.settings.alert_min_score and not existing:
            return None
        ts = now_iso()
        who = ", ".join(sorted({o["org"] for o in a.orgs})) or ", ".join(a.sectors) or "unattributed"
        label = a.categories[0]["label"] if a.categories else "Suspicious post"
        title = f"{label} — {who}"
        summary = (item["body_text"] or "")[:280]
        cats = json.dumps([{k: c[k] for k in ("category", "label", "confidence")} for c in a.categories])
        orgs = json.dumps(a.orgs)
        sectors = json.dumps(sorted({o["sector"] for o in a.orgs} | set(a.sectors)))
        factors = json.dumps({"factors": a.factors, "reasons": a.reasons})
        if existing:
            self.conn.execute(
                "UPDATE alerts SET updated_at=?, severity=?, score=?, title=?, summary=?, categories_json=?, orgs_json=?, "
                "sectors_json=?, factors_json=? WHERE id=?",
                (ts, a.severity, a.score, title, summary, cats, orgs, sectors, factors, existing["id"]))
            alert_id, event = existing["id"], "alert_updated"
        else:
            alert_id = self.conn.execute(
                "INSERT INTO alerts(created_at, updated_at, item_id, source_id, severity, score, title, summary, "
                "categories_json, orgs_json, sectors_json, factors_json, status, provisional, detection_lag_s) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                (ts, ts, item["id"], item["source_id"], a.severity, a.score, title, summary, cats, orgs, sectors, factors,
                 "new" if fresh else "historical", item["detection_lag_s"])).lastrowid
            event = "alert_new"
        self.audit.append("vigiles", event, f"item:{item['id']}", a.severity,
                          {"alert": alert_id, "score": a.score, "fresh": fresh, "title": title[:200]})
        payload = self.payload(alert_id)
        self.bus.publish({"type": event, "alert": payload})
        if fresh and event == "alert_new" and self.settings.telegram_bot_token:
            asyncio.get_running_loop().create_task(self._push_when_settled(alert_id))
        return payload

    async def _push_when_settled(self, alert_id: int, wait_s: float = 6.0) -> None:
        """Page an officer only after the deep lane has had its say (it normally answers in ~1 s), so a recycled
        or fake leak that the fast lane rated CRITICAL never wakes anyone up. Falls back to the fast verdict."""
        loop = asyncio.get_running_loop()
        started = loop.time()
        while loop.time() - started < wait_s:
            row = self.conn.execute("SELECT provisional FROM alerts WHERE id=?", (alert_id,)).fetchone()
            if row and row["provisional"] == 0:
                break
            await asyncio.sleep(0.5)
        p = self.payload(alert_id)
        if p.get("severity") in PUSH_SEVERITIES:
            await self._telegram(p)
        else:
            self.audit.append("vigiles", "push_suppressed", f"alert:{alert_id}", p.get("severity", "?"),
                              {"reason": "deep lane downgraded the alert before paging"})

    def update_deep(self, item_id: int, deep: dict) -> dict | None:
        """Upgrade a provisional alert with deep-lane findings. Fast-lane reasons are kept alongside."""
        row = self.conn.execute("SELECT id, severity, score, factors_json FROM alerts WHERE item_id=?", (item_id,)).fetchone()
        if not row:
            if deep["score"] < self.settings.alert_min_score:
                return None
            item = self.conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
            ts = now_iso()
            fresh = item["detection_lag_s"] is not None and item["detection_lag_s"] <= 86400
            self.conn.execute(
                "INSERT INTO alerts(created_at, updated_at, item_id, source_id, severity, score, title, summary, "
                "categories_json, orgs_json, sectors_json, factors_json, status, provisional, detection_lag_s) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
                (ts, ts, item_id, item["source_id"], deep["severity"], deep["score"], deep["title"],
                 (item["body_text"] or "")[:280], "[]", "[]", "[]", json.dumps({"reasons": []}),
                 "new" if fresh else "historical", item["detection_lag_s"]))
            row = self.conn.execute("SELECT id, severity, score, factors_json FROM alerts WHERE item_id=?",
                                    (item_id,)).fetchone()
            self.audit.append("vigiles", "alert_new", f"item:{item_id}", deep["severity"],
                              {"alert": row["id"], "score": deep["score"], "origin": "deep lane", "title": deep["title"][:200]})
        fj = json.loads(row["factors_json"] or "{}")
        fj.setdefault("fast", {"severity": row["severity"], "score": row["score"]})
        prev = fj.get("deep") or {}
        fj["deep"] = {"severity": deep["severity"], "score": deep["score"], "reasons": deep["reasons"],
                      "factors": deep["factors"], "authenticity": deep["authenticity"]["verdict"],
                      "actor": ((deep.get("attribution") or {}).get("actor") or {}).get("label"),
                      "assessed_at": deep["assessed_at"], "latency_s": deep.get("latency_s"),
                      # the first ruling is the one that cleared or returned the message; later passes only re-check it
                      "first_assessed_at": prev.get("first_assessed_at") or prev.get("assessed_at") or deep["assessed_at"]}
        self.conn.execute("UPDATE alerts SET severity=?, score=?, provisional=0, factors_json=?, updated_at=? WHERE id=?",
                          (deep["severity"], deep["score"], json.dumps(fj), now_iso(), row["id"]))
        if row["severity"] != deep["severity"]:
            self.audit.append("vigiles", "alert_rescored", f"item:{item_id}", deep["severity"],
                              {"from": row["severity"], "to": deep["severity"], "score": deep["score"],
                               "authenticity": deep["authenticity"]["verdict"]})
        payload = self.payload(row["id"])
        self.bus.publish({"type": "alert_updated", "deep": True, "alert": payload})
        return payload

    def item_gone(self, item_id: int, how: str, lifetime_s: float | None) -> None:
        self.conn.execute("UPDATE alerts SET deleted=1, updated_at=? WHERE item_id=?", (now_iso(), item_id))
        row = self.conn.execute("SELECT id FROM alerts WHERE item_id=?", (item_id,)).fetchone()
        self.bus.publish({"type": "item_gone", "item_id": item_id, "how": how, "lifetime_s": lifetime_s,
                          "alert": self.payload(row["id"]) if row else None})

    def payload(self, alert_id: int) -> dict:
        r = self.conn.execute(
            "SELECT a.*, i.title AS item_title, i.author, i.url, i.kind, i.posted_at, i.first_seen, i.deleted_at, "
            "i.first_capture_sha, s.name AS source_name, s.simulated FROM alerts a JOIN items i ON i.id=a.item_id "
            "JOIN sources s ON s.id=a.source_id WHERE a.id=?", (alert_id,)).fetchone()
        if not r:
            return {}
        d = {k: r[k] for k in r.keys() if not k.endswith("_json")}
        d["summary"] = mask_pii(d["summary"] or "")  # readable copies never carry raw identifiers
        d["item_title"] = mask_pii(d["item_title"] or "")
        d["categories"] = json.loads(r["categories_json"] or "[]")
        d["orgs"] = json.loads(r["orgs_json"] or "[]")
        d["sectors"] = json.loads(r["sectors_json"] or "[]")
        d.update(json.loads(r["factors_json"] or "{}"))
        return d

    async def _telegram(self, p: dict) -> None:
        deep = p.get("deep") or {}
        lines = [f"🚨 LIBERTAS · {p['severity']} (score {p['score']})", p["title"], f"Source: {p['source_name']}",
                 f"Posted: {p['posted_at']}", f"Detected: {p['first_seen']} (lag {p['detection_lag_s']} s)"]
        if deep:
            lines += [f"Authenticity: {deep.get('authenticity')}"] + [f"• {r[:200]}" for r in deep.get("reasons", [])[1:3]]
        else:
            lines.append("(fast-lane verdict; deep lane still running)")
        if p.get("simulated"):
            lines.append("⚠ SIMULATION data (ShadowNet)")
        text = "\n".join(lines)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage",
                                      json={"chat_id": self.settings.telegram_chat_id, "text": text})
            self.audit.append("vigiles", "telegram_push", f"alert:{p['id']}", "sent" if r.status_code == 200 else "failed",
                              {"status": r.status_code})
        except httpx.HTTPError as exc:
            self.log(f"telegram push failed: {exc}")
