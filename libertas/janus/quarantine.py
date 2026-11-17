"""Quarantine store: raw responses kept only as evidence.

Blobs are gzip-compressed, named by the SHA-256 of the *uncompressed* bytes, and have NO file extension,
so no program on the machine (double-click, previewer, indexer) will open or run them by accident.
"""
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path


class IntegrityError(Exception):
    pass


class Quarantine:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path_for(self, sha256: str) -> Path:
        return self.root / sha256[:2] / sha256

    def put(self, raw: bytes) -> str:
        sha = hashlib.sha256(raw).hexdigest()
        path = self.path_for(sha)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.parent / (sha + "-partial")
            tmp.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
            tmp.replace(path)
        return sha

    def get(self, sha256: str) -> bytes:
        raw = gzip.decompress(self.path_for(sha256).read_bytes())
        if hashlib.sha256(raw).hexdigest() != sha256:
            raise IntegrityError(f"quarantine blob {sha256} failed integrity check")
        return raw

    def exists(self, sha256: str) -> bool:
        return self.path_for(sha256).exists()
