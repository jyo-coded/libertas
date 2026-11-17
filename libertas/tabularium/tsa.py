"""RFC 3161 trusted timestamps.

Libertas sends the TSA nothing but a SHA-256 digest (a Merkle root). The signed token proves that the root,
and so every capture under it, existed no later than the TSA's genTime. Verification checks the status, that
the message imprint equals our digest, the nonce, the messageDigest attribute, and the CMS signature against the
certificate embedded in the token. Chain validation against the TSA's CA is left to `openssl ts -verify -CAfile`,
and to an Indian licensed CA's TSA in production.
"""
from __future__ import annotations

import hashlib
import secrets

from asn1crypto import tsp
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

_HASHES = {"sha1": hashes.SHA1, "sha256": hashes.SHA256, "sha384": hashes.SHA384, "sha512": hashes.SHA512}


class TSAError(Exception):
    pass


def build_request(digest: bytes, nonce: int | None = None) -> tuple[bytes, int]:
    nonce = nonce if nonce is not None else secrets.randbits(63)
    req = tsp.TimeStampReq({
        "version": 1,
        "message_imprint": {"hash_algorithm": {"algorithm": "sha256"}, "hashed_message": digest},
        "nonce": nonce,
        "cert_req": True,
    })
    return req.dump(), nonce


def _verify_cms_signature(signed_data) -> tuple[bool, str, str, str]:
    signer = signed_data["signer_infos"][0]
    certs = [c.chosen for c in (signed_data["certificates"] or []) if c.name == "certificate"]
    sid = signer["sid"]
    cert = None
    for c in certs:
        if sid.name == "issuer_and_serial_number":
            if c.serial_number == sid.chosen["serial_number"].native and c.issuer == sid.chosen["issuer"]:
                cert = c
        elif c.key_identifier == sid.chosen.native:
            cert = c
    if cert is None:
        return False, "", "", "signing certificate not included in the token"
    names = cert.subject.native
    subject = ", ".join(x for x in (names.get("common_name"), names.get("organization_name"),
                                    names.get("country_name")) if x) or cert.subject.human_friendly
    fingerprint = hashlib.sha256(cert.dump()).hexdigest()
    digest_alg = signer["digest_algorithm"]["algorithm"].native
    hash_cls = _HASHES.get(digest_alg)
    if hash_cls is None:
        return False, subject, fingerprint, f"unsupported digest {digest_alg}"
    content = signed_data["encap_content_info"]["content"].contents
    attrs = signer["signed_attrs"]
    md = next((a["values"][0].native for a in attrs if a["type"].native == "message_digest"), None)
    if md != hashlib.new(digest_alg, content).digest():
        return False, subject, fingerprint, "messageDigest attribute does not match the timestamp content"
    to_verify = b"\x31" + attrs.dump()[1:]  # signature covers the attributes encoded as a SET OF
    public_key = cx509.load_der_x509_certificate(cert.dump()).public_key()
    signature = signer["signature"].native
    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            if "pss" in signer["signature_algorithm"]["algorithm"].native:
                public_key.verify(signature, to_verify,
                                  padding.PSS(mgf=padding.MGF1(hash_cls()), salt_length=padding.PSS.AUTO), hash_cls())
            else:
                public_key.verify(signature, to_verify, padding.PKCS1v15(), hash_cls())
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature, to_verify, ec.ECDSA(hash_cls()))
        else:
            return False, subject, fingerprint, "unsupported key type"
    except Exception as exc:
        return False, subject, fingerprint, f"signature invalid: {type(exc).__name__}"
    return True, subject, fingerprint, ""


def inspect_response(tsr: bytes, digest: bytes, nonce: int | None = None) -> dict:
    resp = tsp.TimeStampResp.load(tsr)
    status = resp["status"]["status"].native
    if status not in ("granted", "granted_with_mods"):
        raise TSAError(f"TSA refused: {status}")
    signed_data = resp["time_stamp_token"]["content"]
    tst = signed_data["encap_content_info"]["content"].parsed
    sig_ok, subject, fingerprint, problem = _verify_cms_signature(signed_data)
    return {
        "status": status,
        "gen_time": tst["gen_time"].native.isoformat(),
        "serial": str(tst["serial_number"].native),
        "policy": tst["policy"].dotted,
        "hash_algorithm": tst["message_imprint"]["hash_algorithm"]["algorithm"].native,
        "imprint_ok": tst["message_imprint"]["hashed_message"].native == digest,
        "nonce_ok": nonce is None or tst["nonce"].native == nonce,
        "signature_ok": sig_ok,
        "signature_problem": problem,
        "tsa_subject": subject,
        "tsa_cert_sha256": fingerprint,
    }
