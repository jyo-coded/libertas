"""Tabularium service: seal new captures into Merkle batches, sign each root, and timestamp it with an RFC 3161 TSA.

Every batch also carries the audit chain's head as a leaf, so the audit log itself is anchored to an external,
independent clock as well.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3

import httpx

from ..common.timeutil import now_iso
from ..config import Settings
from ..lex.audit import AuditLog
from .merkle import audit_leaf, canonical, capture_leaf, leaf_hash, merkle_proof, merkle_root
from .signing import Signer
from .tsa import TSAError, build_request, inspect_response


class Tabularium:
    def __init__(self, conn: sqlite3.Connection, audit: AuditLog, signer: Signer, settings: Settings, log=print,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.conn, self.audit, self.signer, self.settings, self.log = conn, audit, signer, settings, log
        self.client = None
        if settings.tsa_enabled:
            kwargs: dict = {"timeout": 30.0, "trust_env": False, "headers": {"User-Agent": "Libertas-Tabularium/0.1"}}
            if transport is not None:
                kwargs["transport"] = transport
            self.client = httpx.AsyncClient(**kwargs)
        self._lock = asyncio.Lock()

    def seal(self) -> dict | None:
        rows = self.conn.execute(
            "SELECT c.id, c.sha256, c.url, c.fetched_at, c.source_id, c.status FROM captures c WHERE c.sha256 IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM batch_leaves bl WHERE bl.kind='capture' AND bl.ref=c.id) ORDER BY c.id").fetchall()
        if not rows:
            return None
        head = self.conn.execute("SELECT seq, hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        leaves = [("capture", r["id"], capture_leaf(r)) for r in rows]
        if head:
            leaves.append(("audit_head", head["seq"], audit_leaf(head["seq"], head["hash"])))
        hashes = [leaf_hash(canonical(data)) for _, _, data in leaves]
        root = merkle_root(hashes)
        batch_id = self.conn.execute(
            "INSERT INTO merkle_batches(created_at, root, size, audit_seq, audit_head, signature, status, tsa_url) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (now_iso(), root.hex(), len(hashes), head["seq"] if head else None, head["hash"] if head else None,
             self.signer.sign(root), "sealed", self.settings.tsa_url if self.client else None)).lastrowid
        self.conn.executemany("INSERT INTO batch_leaves(batch_id, leaf_index, kind, ref, leaf_hash) VALUES (?,?,?,?,?)",
                              [(batch_id, i, kind, ref, h.hex()) for i, ((kind, ref, _), h) in enumerate(zip(leaves, hashes))])
        self.audit.append("tabularium", "batch_sealed", f"batch:{batch_id}", "sealed",
                          {"root": root.hex(), "leaves": len(hashes)})
        return {"id": batch_id, "root": root.hex(), "size": len(hashes)}

    async def timestamp_pending(self) -> int:
        if not self.client:
            return 0
        done = 0
        rows = self.conn.execute("SELECT id, root FROM merkle_batches WHERE status IN ('sealed', 'tsa_pending') "
                                 "ORDER BY id LIMIT 20").fetchall()
        for r in rows:
            root = bytes.fromhex(r["root"])
            try:
                der, nonce = build_request(root)
                resp = await self.client.post(self.settings.tsa_url, content=der,
                                              headers={"Content-Type": "application/timestamp-query"})
                resp.raise_for_status()
                info = inspect_response(resp.content, root, nonce)
                if not (info["imprint_ok"] and info["nonce_ok"]):
                    raise TSAError("token does not cover our digest or nonce")
                self.conn.execute("UPDATE merkle_batches SET status='timestamped', tsr=?, tsa_gen_time=?, tsa_info_json=?, "
                                  "error=NULL WHERE id=?", (resp.content, info["gen_time"], json.dumps(info), r["id"]))
                self.audit.append("tabularium", "batch_timestamped", f"batch:{r['id']}", "ok",
                                  {"gen_time": info["gen_time"], "serial": info["serial"],
                                   "tsa": info["tsa_subject"][:160], "signature_ok": info["signature_ok"]})
                done += 1
            except (httpx.HTTPError, TSAError, ValueError) as exc:
                self.conn.execute("UPDATE merkle_batches SET status='tsa_pending', error=? WHERE id=?",
                                  (f"{type(exc).__name__}: {exc}"[:300], r["id"]))
                self.log(f"timestamp authority unavailable ({type(exc).__name__}); batch {r['id']} will retry")
                break
        return done

    async def ensure_sealed(self) -> None:
        """Seal anything new and timestamp it now (used before building an evidence pack)."""
        async with self._lock:
            self.seal()
            await self.timestamp_pending()

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.settings.seal_interval_s)
            try:
                await self.ensure_sealed()
            except Exception as exc:
                self.log(f"tabularium cycle failed: {type(exc).__name__}: {exc}")

    def proof(self, kind: str, ref: int) -> dict | None:
        leaf = self.conn.execute("SELECT batch_id, leaf_index, leaf_hash FROM batch_leaves WHERE kind=? AND ref=?",
                                 (kind, ref)).fetchone()
        if not leaf:
            return None
        leaves = [bytes.fromhex(r[0]) for r in self.conn.execute(
            "SELECT leaf_hash FROM batch_leaves WHERE batch_id=? ORDER BY leaf_index", (leaf["batch_id"],))]
        batch = self.conn.execute("SELECT root FROM merkle_batches WHERE id=?", (leaf["batch_id"],)).fetchone()
        return {"batch_id": leaf["batch_id"], "leaf_index": leaf["leaf_index"], "leaf_hash": leaf["leaf_hash"],
                "path": merkle_proof(leaves, leaf["leaf_index"]), "root": batch["root"]}

    async def aclose(self) -> None:
        if self.client:
            await self.client.aclose()
