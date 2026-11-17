"""Tamper-evident audit log: every entry's hash covers the previous entry's hash (blueprint §15)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading

from ..common.timeutil import now_iso

GENESIS = "0" * 64


def _canonical(ts: str, actor: str, action: str, target: str, decision: str, detail: dict) -> str:
    body = {"ts": ts, "actor": actor, "action": action, "target": target, "decision": decision, "detail": detail}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AuditLog:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.Lock()

    def append(self, actor: str, action: str, target: str = "", decision: str = "", detail: dict | None = None) -> str:
        detail = detail or {}
        with self._lock:
            row = self.conn.execute("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row[0] if row else GENESIS
            ts = now_iso()
            digest = hashlib.sha256((prev + _canonical(ts, actor, action, target, decision, detail)).encode()).hexdigest()
            self.conn.execute(
                "INSERT INTO audit_log(ts, actor, action, target, decision, detail_json, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?)",
                (ts, actor, action, target, decision,
                 json.dumps(detail, sort_keys=True, separators=(",", ":"), ensure_ascii=False), prev, digest))
            return digest

    def verify(self) -> dict:
        prev, count = GENESIS, 0
        rows = self.conn.execute(
            "SELECT seq, ts, actor, action, target, decision, detail_json, prev_hash, hash FROM audit_log ORDER BY seq")
        for seq, ts, actor, action, target, decision, detail_json, prev_hash, digest in rows:
            expected = hashlib.sha256(
                (prev + _canonical(ts, actor, action, target, decision, json.loads(detail_json))).encode()).hexdigest()
            if prev_hash != prev or digest != expected:
                return {"ok": False, "entries_checked": count, "broken_at_seq": seq}
            prev, count = digest, count + 1
        return {"ok": True, "entries_checked": count, "head": prev}
