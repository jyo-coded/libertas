#!/usr/bin/env python3
"""Independent verifier for a Libertas evidence pack. It does NOT use any Libertas code.

Usage:   python verify.py [PACK_DIRECTORY]

Checks
  1. every file listed in manifest.json matches its SHA-256 and MD5;
  2. manifest.json carries a valid Ed25519 signature (manifest.sig) from the key in signing_key.pub;
  3. every capture's Merkle inclusion proof leads to its batch root, and each batch root is signed;
  4. every RFC 3161 timestamp token covers its batch root (needs the 'asn1crypto' package).
Optional packages: cryptography (checks 2 and 3), asn1crypto (check 4). Without them those checks are SKIPPED and the
equivalent OpenSSL commands are printed. Exit code: 0 = all passed, 1 = a check failed, 3 = passed but some skipped.
"""
import hashlib
import json
import sys
from pathlib import Path


def _hash_file(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def leaf_hash(data):
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left, right):
    return hashlib.sha256(b"\x01" + left + right).digest()


def verify_path(leaf, path, root):
    h = leaf
    for step in path:
        sibling = bytes.fromhex(step["hash"])
        h = node_hash(sibling, h) if step["side"] == "L" else node_hash(h, sibling)
    return h == root


class Tally:
    def __init__(self):
        self.passed = self.failed = self.skipped = 0

    def ok(self, msg):
        self.passed += 1
        print(f"  [PASS] {msg}")

    def bad(self, msg):
        self.failed += 1
        print(f"  [FAIL] {msg}")

    def skip(self, msg):
        self.skipped += 1
        print(f"  [SKIP] {msg}")


def main(argv):
    pack = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent
    raw = (pack / "manifest.json").read_bytes()
    m = json.loads(raw)
    t = Tally()
    print(f"Libertas evidence pack {m['pack_id']}  (format {m['format']})")
    print(f"Generated {m['generated_at_utc']} UTC by {m['generated_by']['system']}")
    if m.get("simulation"):
        print("NOTE: this pack was produced from SIMULATED data (ShadowNet).")

    print("\n1. File integrity")
    for f in m["files"]:
        p = pack / f["path"]
        if not p.exists():
            t.bad(f"missing file {f['path']}")
        elif _hash_file(p, "sha256") != f["sha256"] or _hash_file(p, "md5") != f["md5"]:
            t.bad(f"hash mismatch: {f['path']}")
        else:
            t.ok(f"{f['path']}  sha256 {f['sha256'][:16]}...")

    print("\n2. Manifest signature (Ed25519)")
    key = None
    try:
        from cryptography.hazmat.primitives import serialization
        key = serialization.load_pem_public_key((pack / m["signing_key"]["public_key_file"]).read_bytes())
        raw_pub = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if hashlib.sha256(raw_pub).hexdigest() != m["signing_key"]["fingerprint_sha256"]:
            t.bad("public key does not match the fingerprint recorded in the manifest")
        key.verify(bytes.fromhex((pack / "manifest.sig").read_text().strip()), raw)
        t.ok(f"manifest.json signed by key {m['signing_key']['fingerprint_sha256'][:16]}...")
    except ImportError:
        t.skip("install the 'cryptography' package to verify signatures")
    except Exception as exc:
        t.bad(f"manifest signature invalid ({type(exc).__name__})")

    print("\n3. Capture inclusion proofs (Merkle)")
    for c in m["captures"]:
        p = pack / c["file"]
        if not p.exists() or _hash_file(p, "sha256") != c["sha256"]:
            t.bad(f"capture {c['capture_id']}: raw file missing or altered")
            continue
        if c["leaf_data"].get("sha256") != c["sha256"]:
            t.bad(f"capture {c['capture_id']}: leaf does not commit to this file")
            continue
        batch = m["batches"][str(c["merkle"]["batch_id"])]
        if verify_path(leaf_hash(canonical(c["leaf_data"])), c["merkle"]["path"], bytes.fromhex(batch["root"])):
            t.ok(f"capture {c['capture_id']} ({c['fetched_at']}) is in batch {c['merkle']['batch_id']}")
        else:
            t.bad(f"capture {c['capture_id']}: Merkle proof does not reach the batch root")
    for bid, b in m["batches"].items():
        if key is None:
            continue
        try:
            key.verify(bytes.fromhex(b["internal_signature"]), bytes.fromhex(b["root"]))
            t.ok(f"batch {bid} root signed by Libertas")
        except Exception:
            t.bad(f"batch {bid}: root signature invalid")

    print("\n4. RFC 3161 timestamps")
    for bid, b in m["batches"].items():
        if not b.get("tsr_file"):
            t.skip(f"batch {bid}: no external timestamp in this pack ({b.get('status')})")
            continue
        tsr = (pack / b["tsr_file"]).read_bytes()
        try:
            from asn1crypto import tsp
            resp = tsp.TimeStampResp.load(tsr)
            status = resp["status"]["status"].native
            tst = resp["time_stamp_token"]["content"]["encap_content_info"]["content"].parsed
            imprint = tst["message_imprint"]["hashed_message"].native
            if status in ("granted", "granted_with_mods") and imprint == bytes.fromhex(b["root"]):
                t.ok(f"batch {bid}: token from {b['tsa'].get('tsa_subject', 'TSA')[:60]} at {tst['gen_time'].native} covers the root")
            else:
                t.bad(f"batch {bid}: token does not cover the batch root")
        except ImportError:
            t.skip(f"batch {bid}: install 'asn1crypto', or run:  openssl ts -reply -in {b['tsr_file']} -text  and  "
                   f"openssl ts -verify -digest {b['root']} -in {b['tsr_file']} -CAfile <TSA CA certificate>")

    print(f"\nResult: {t.passed} passed, {t.failed} failed, {t.skipped} skipped")
    if t.failed:
        print("VERIFICATION FAILED")
        return 1
    print("ALL CHECKS PASSED" if not t.skipped else "PASSED (some checks skipped)")
    return 0 if not t.skipped else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
