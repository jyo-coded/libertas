"""v3 onion address helpers: checksum validation, extraction, and (for tests) minting valid unused addresses."""
from __future__ import annotations

import base64
import hashlib
import re
import secrets

_LABEL_RE = re.compile(r"^[a-z2-7]{56}$")
ONION_IN_TEXT = re.compile(r"\b((?:[a-z0-9-]+\.)*[a-z2-7]{56})\.onion\b", re.IGNORECASE)


def onion_label(host: str) -> str | None:
    """Return the 56-char v3 label of a host like 'www.<label>.onion', or None."""
    host = (host or "").strip().lower().rstrip(".")
    if not host.endswith(".onion"):
        host = host + ".onion" if _LABEL_RE.match(host) else host
    if not host.endswith(".onion"):
        return None
    label = host[: -len(".onion")].split(".")[-1]
    return label if _LABEL_RE.match(label) else None


def is_valid_v3(host_or_label: str) -> bool:
    label = onion_label(host_or_label)
    if not label:
        return False
    raw = base64.b32decode(label.upper())
    pub, chk, ver = raw[:32], raw[32:34], raw[34:35]
    return ver == b"\x03" and hashlib.sha3_256(b".onion checksum" + pub + ver).digest()[:2] == chk


def find_onions(text: str) -> list[str]:
    """Valid v3 onion labels mentioned in text (deduplicated, order kept)."""
    seen: dict[str, None] = {}
    for m in ONION_IN_TEXT.finditer(text or ""):
        label = onion_label(m.group(0))
        if label and is_valid_v3(label):
            seen.setdefault(label, None)
    return list(seen)


# --- minimal ed25519 base-point multiplication, used only to mint valid-but-unused test addresses ---
_q = 2**255 - 19
_d = (-121665 * pow(121666, _q - 2, _q)) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_d * y * y + 1, _q - 2, _q)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q:
        x = (x * _I) % _q
    return _q - x if x % 2 else x


_BY = (4 * pow(5, _q - 2, _q)) % _q
_B = (_xrecover(_BY), _BY)


def _add(p, q):
    x1, y1 = p
    x2, y2 = q
    t = _d * x1 * x2 * y1 * y2
    return ((x1 * y2 + x2 * y1) * pow(1 + t, _q - 2, _q) % _q, (y1 * y2 + x1 * x2) * pow(1 - t, _q - 2, _q) % _q)


def _mul(p, e: int):
    r = (0, 1)
    while e:
        if e & 1:
            r = _add(r, p)
        p = _add(p, p)
        e >>= 1
    return r


def random_v3_label() -> str:
    a = int.from_bytes(secrets.token_bytes(32), "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    x, y = _mul(_B, a)
    pub = (y | ((x & 1) << 255)).to_bytes(32, "little")
    chk = hashlib.sha3_256(b".onion checksum" + pub + b"\x03").digest()[:2]
    return base64.b32encode(pub + chk + b"\x03").decode().lower()
