"""India identifier pack (blueprint #12): detection and validation. Values are masked and hashed on ingest.

SIMULATION profile: ShadowNet generates Aadhaar-format numbers starting with 1 and mobiles starting with 5.
UIDAI never issues Aadhaar numbers starting with 0 or 1, and Indian mobiles start with 6-9, so synthetic
values can never belong to a real person. The validators accept them only when simulation=True.
"""
from __future__ import annotations

import re

_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]  # rotations 1-4 invert to 4-1; reflections 5-9 are self-inverse


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_digit(number: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


_GST = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_valid(g: str) -> bool:
    g = g.upper()
    if len(g) != 15 or any(ch not in _GST for ch in g):
        return False
    total, factor = 0, 1
    for ch in g[:14]:
        prod = _GST.index(ch) * factor
        total += prod // 36 + prod % 36
        factor = 2 if factor == 1 else 1
    return _GST[(36 - total % 36) % 36] == g[14]


PAN_HOLDER_TYPES = {"P": "individual", "C": "company", "H": "HUF", "F": "firm", "A": "association of persons",
                    "T": "trust", "B": "body of individuals", "L": "local authority",
                    "J": "artificial juridical person", "G": "government"}

AADHAAR_RE = re.compile(r"(?<![\w-])(\d{4})[ -]?(\d{4})[ -]?(\d{4})(?![\w-])")
_HEX_GROUP_BEFORE = re.compile(r"[0-9A-Fa-f]{4} $")
_HEX_GROUP_AFTER = re.compile(r"^ [0-9A-Fa-f]{4}")
PAN_RE = re.compile(r"\b([A-Z]{3}[ABCFGHJLPT][A-Z]\d{4}[A-Z])\b")
GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
MOBILE_RE = re.compile(r"(?<![\w+])(?:\+?91[ -]?|0)?([5-9]\d{4})[ -]?(\d{5})(?!\w)")
UPI_PSPS = ("okaxis", "oksbi", "okhdfcbank", "okicici", "ybl", "ibl", "axl", "paytm", "ptyes", "ptaxis", "pthdfc",
            "ptsbi", "upi", "apl", "yapl", "ikwik", "fbl", "airtel", "jio", "kotak", "icici", "hdfcbank", "sbi",
            "axisbank", "freecharge", "waaxis", "wahdfcbank", "wasbi", "abfspay", "naviaxis", "superyes")
UPI_RE = re.compile(r"\b([a-zA-Z0-9._-]{2,64})@(" + "|".join(UPI_PSPS) + r")(?![.\w])", re.IGNORECASE)
INDIAN_DOMAIN_RE = re.compile(r"\b[a-z0-9.-]+\.(gov\.in|nic\.in|ac\.in|edu\.in|res\.in|co\.in|org\.in|in)\b", re.I)


def aadhaar_candidates(text: str, *, simulation: bool = False) -> list[tuple[str, bool]]:
    """(12-digit number, valid) pairs. Valid = Verhoeff passes and the first digit is issuable."""
    out = []
    for m in AADHAAR_RE.finditer(text):
        # skip runs that are part of a longer group sequence, e.g. a PGP fingerprint "ABCD 1234 5678 9012 EF01"
        if _HEX_GROUP_BEFORE.search(text[max(0, m.start() - 5):m.start()]) or _HEX_GROUP_AFTER.match(text[m.end():m.end() + 5]):
            continue
        num = "".join(m.groups())
        first_ok = num[0] in "23456789" or (simulation and num[0] == "1")
        if num[0] == "0":
            continue
        out.append((num, first_ok and verhoeff_valid(num)))
    return out


def mobile_candidates(text: str, *, simulation: bool = False) -> list[str]:
    out = []
    for m in MOBILE_RE.finditer(text):
        num = m.group(1) + m.group(2)
        if num[0] in "6789" or (simulation and num[0] == "5"):
            out.append(num)
    return out


def mask_digits(value: str, keep: int = 4) -> str:
    return "X" * max(0, len(value) - keep) + value[-keep:]


_EMAIL_MASK = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,24})\b")


# Personal names in leaked sample tables. A row is treated as personal data once it carries a masked identifier;
# its name cell (the column headed "name", or a name-like first cell) is then masked to an initial: "S****** P.".
_NAME_TOKEN = re.compile(r"^(?:[A-Z][A-Za-z'’-]{1,30}\.?|[A-Z]\.?)$")
_MASKED_ID = re.compile(r"XXXX XXXX \d{4}|\+91 XXXXXX\d{4}|\*\*\*@")
_CELL_SPLIT = re.compile(r"(\s*[|;\t,]\s*)")
_NAME_HEADERS = {"name", "full name", "fullname", "customer name", "patient name", "student name", "employee name",
                 "subscriber name", "holder name", "account name", "first name", "last name", "member name"}


def _looks_like_name(cell: str) -> bool:
    toks = cell.split()
    return 1 <= len(toks) <= 5 and all(_NAME_TOKEN.match(t) for t in toks) and any(len(t.rstrip(".")) > 1 for t in toks)


def _mask_name(cell: str) -> str:
    def one(tok: str) -> str:
        core = tok.rstrip(".")
        return tok if len(core) <= 1 else core[0] + "*" * (len(core) - 1) + tok[len(core):]
    return " ".join(one(t) for t in cell.split())


def _mask_names(text: str) -> str:
    lines, name_cols = [], set()
    for line in text.split("\n"):
        parts = _CELL_SPLIT.split(line)  # cells at even indexes, delimiters at odd ones
        cells = parts[0::2]
        if len(cells) >= 2:
            headers = {i for i, c in enumerate(cells) if c.strip().lower() in _NAME_HEADERS}
            if headers:
                name_cols = headers
                lines.append(line)
                continue
            if _MASKED_ID.search(line):
                for i, c in enumerate(cells):
                    core = c.strip()
                    if (i in name_cols or i == 0) and _looks_like_name(core):
                        parts[2 * i] = c.replace(core, _mask_name(core))
                line = "".join(parts)
        lines.append(line)
    return "\n".join(lines)


def mask_pii(text: str) -> str:
    """Mask Aadhaar-format numbers, Indian mobiles, email local parts and the personal names beside them in sample
    rows, for human-readable outputs. Original captures keep the exact bytes; only reports and readable copies are masked."""
    out, last = [], 0
    for m in AADHAAR_RE.finditer(text or ""):
        if _HEX_GROUP_BEFORE.search(text[max(0, m.start() - 5):m.start()]) or _HEX_GROUP_AFTER.match(text[m.end():m.end() + 5]):
            continue
        num = "".join(m.groups())
        if num[0] == "0":
            continue
        out += [text[last:m.start()], f"XXXX XXXX {num[-4:]}"]
        last = m.end()
    out.append((text or "")[last:])
    masked = MOBILE_RE.sub(lambda m: "+91 XXXXXX" + (m.group(1) + m.group(2))[-4:], "".join(out))
    return _mask_names(_EMAIL_MASK.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", masked))
