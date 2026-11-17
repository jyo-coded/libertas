"""Evidence signing key (Ed25519). Phase 0 keeps it in var/keys; production keeps it in an HSM."""
from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class Signer:
    def __init__(self, key_path: Path):
        key_path = Path(key_path)
        if key_path.exists():
            self._key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        else:
            self._key = Ed25519PrivateKey.generate()
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(self._key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                         serialization.NoEncryption()))
        pub = self._key.public_key()
        self.public_pem = pub.public_bytes(serialization.Encoding.PEM,
                                           serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.fingerprint = hashlib.sha256(raw).hexdigest()

    def sign(self, data: bytes) -> str:
        return self._key.sign(data).hex()

    @staticmethod
    def verify(public_pem: str, data: bytes, signature_hex: str) -> bool:
        key = serialization.load_pem_public_key(public_pem.encode())
        if not isinstance(key, Ed25519PublicKey):
            return False
        try:
            key.verify(bytes.fromhex(signature_hex), data)
            return True
        except (InvalidSignature, ValueError):
            return False
