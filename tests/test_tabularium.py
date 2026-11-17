"""Merkle proofs and RFC 3161 token verification (against a real FreeTSA token kept as a fixture)."""
import hashlib
from pathlib import Path

import pytest

from libertas.tabularium.merkle import leaf_hash, merkle_proof, merkle_root, verify_proof
from libertas.tabularium.signing import Signer
from libertas.tabularium.tsa import build_request, inspect_response

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 9, 16, 33])
def test_every_leaf_proves_into_the_root(n):
    leaves = [leaf_hash(f"capture-{i}".encode()) for i in range(n)]
    root = merkle_root(leaves)
    for i, leaf in enumerate(leaves):
        assert verify_proof(leaf, merkle_proof(leaves, i), root)
    tampered = leaf_hash(b"capture-0-altered")
    assert not verify_proof(tampered, merkle_proof(leaves, 0), root)


def test_real_freetsa_token_verifies():
    digest = hashlib.sha256((FIXTURES / "freetsa_probe.txt").read_bytes()).digest()
    info = inspect_response((FIXTURES / "freetsa_probe.tsr").read_bytes(), digest)
    assert info["status"] == "granted" and info["imprint_ok"] and info["hash_algorithm"] == "sha256"
    assert info["signature_ok"], info["signature_problem"]
    assert "freetsa" in info["tsa_subject"].lower() and info["gen_time"].startswith("2026-11-17")
    wrong = inspect_response((FIXTURES / "freetsa_probe.tsr").read_bytes(), b"\x00" * 32)
    assert not wrong["imprint_ok"]


def test_request_encoding_and_signer(tmp_path):
    der, nonce = build_request(b"\x11" * 32, nonce=42)
    assert der[0] == 0x30 and nonce == 42 and b"\x11" * 32 in der
    signer = Signer(tmp_path / "k.pem")
    sig = signer.sign(b"root")
    assert Signer.verify(signer.public_pem, b"root", sig) and not Signer.verify(signer.public_pem, b"r00t", sig)
    assert Signer(tmp_path / "k.pem").fingerprint == signer.fingerprint  # key persists
