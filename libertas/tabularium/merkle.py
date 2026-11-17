"""Merkle trees over capture records (RFC 6962-style domain separation: 0x00 for leaves, 0x01 for nodes).

One RFC 3161 token on a batch root timestamps every capture in that batch. A capture's inclusion proof is
the list of sibling hashes from its leaf up to that root. Odd nodes are promoted to the next level unchanged.
The same rules are re-implemented in the standalone verify.py that ships inside every evidence pack.
"""
from __future__ import annotations

import hashlib
import json


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _next_level(level: list[bytes]) -> list[bytes]:
    return [node_hash(level[i], level[i + 1]) if i + 1 < len(level) else level[i] for i in range(0, len(level), 2)]


def merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        return hashlib.sha256(b"").digest()
    level = list(leaves)
    while len(level) > 1:
        level = _next_level(level)
    return level[0]


def merkle_proof(leaves: list[bytes], index: int) -> list[dict]:
    path, level, i = [], list(leaves), index
    while len(level) > 1:
        sibling = i ^ 1
        if sibling < len(level):
            path.append({"side": "L" if sibling < i else "R", "hash": level[sibling].hex()})
        level, i = _next_level(level), i // 2
    return path


def verify_proof(leaf: bytes, path: list[dict], root: bytes) -> bool:
    h = leaf
    for step in path:
        sibling = bytes.fromhex(step["hash"])
        h = node_hash(sibling, h) if step["side"] == "L" else node_hash(h, sibling)
    return h == root


def capture_leaf(row) -> dict:
    return {"type": "capture", "capture_id": row["id"], "sha256": row["sha256"], "url": row["url"],
            "fetched_at": row["fetched_at"], "source_id": row["source_id"], "status": row["status"]}


def audit_leaf(seq: int, head: str) -> dict:
    return {"type": "audit_head", "seq": seq, "hash": head}
