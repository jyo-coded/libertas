"""Indicator extraction (blueprint #11, #12). Personal identifiers are never stored in clear: they become a
keyed hash (HMAC-SHA256 with a per-installation secret, so items can still be matched to each other) plus a
masked display value."""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import asdict, dataclass

from ..common.onion import find_onions
from . import india
from .cryptoaddr import find_wallets

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b")
DOMAIN_RE = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:example|in|com|org|net|io|info|biz|ru|cn|xyz|top))\b", re.I)
PGP_FP_RE = re.compile(r"\b((?:[0-9A-F]{4} ?){9}[0-9A-F]{4})\b")
TOX_RE = re.compile(r"\b([0-9A-F]{76})\b")
SESSION_RE = re.compile(r"\b(05[0-9a-f]{64})\b")
JABBER_RE = re.compile(r"(?:jabber|xmpp)[:\s]+([A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.[a-z]{2,24})", re.I)
TELEGRAM_RE = re.compile(r"(?:\btg\b|telegram|t\.me/)[:\s@/]*@?([A-Za-z][A-Za-z0-9_]{4,31})", re.I)
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)


@dataclass
class Indicator:
    kind: str
    value: str
    display: str
    valid: bool | None
    sensitive: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


class Extractor:
    def __init__(self, secret: bytes, *, simulation: bool = False):
        self.secret = secret
        self.simulation = simulation

    def _h(self, kind: str, value: str) -> str:
        return hmac.new(self.secret, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()

    def extract(self, text: str) -> tuple[list[Indicator], dict]:
        found: dict[tuple[str, str], Indicator] = {}
        stats = {"aadhaar_total": 0, "aadhaar_valid": 0, "mobile_total": 0, "email_total": 0}

        def add(ind: Indicator) -> None:
            found.setdefault((ind.kind, ind.value), ind)

        for w in find_wallets(text):
            net = w["info"].get("network")
            add(Indicator(f"wallet_{w['chain'].lower()}", w["address"], w["address"] + (f" ({net})" if net else ""),
                          w["valid"]))
        for label in find_onions(text):
            add(Indicator("onion", label, label + ".onion", True))
        for m in PGP_FP_RE.finditer(text):
            fp = m.group(1).replace(" ", "")
            add(Indicator("pgp_fingerprint", fp, " ".join(fp[i:i + 4] for i in range(0, 40, 4)), True))
        for m in TOX_RE.finditer(text):
            add(Indicator("tox_id", m.group(1), m.group(1)[:12] + "…" + m.group(1)[-6:], True))
        for m in SESSION_RE.finditer(text):
            add(Indicator("session_id", m.group(1), m.group(1)[:12] + "…" + m.group(1)[-6:], True))
        jabbers = set()
        for m in JABBER_RE.finditer(text):
            jabbers.add(m.group(1).lower())
            add(Indicator("jabber", m.group(1).lower(), m.group(1).lower(), True))
        for m in TELEGRAM_RE.finditer(text):
            add(Indicator("telegram", m.group(1).lower(), "@" + m.group(1).lower(), True))
        for m in CVE_RE.finditer(text):
            add(Indicator("cve", m.group(0).upper(), m.group(0).upper(), True))
        email_domains = set()
        for m in EMAIL_RE.finditer(text):
            email = m.group(0).lower()
            if email in jabbers:
                continue
            local, dom = email.split("@", 1)
            email_domains.add(dom)
            stats["email_total"] += 1
            add(Indicator("email", self._h("email", email), f"{local[0]}***@{dom}", True, True))
        for m in DOMAIN_RE.finditer(text):
            dom = m.group(1).lower()
            if not dom.endswith(".onion"):
                add(Indicator("domain", dom, dom, True))
        for dom in email_domains:
            add(Indicator("domain", dom, dom, True))
        for num, valid in india.aadhaar_candidates(text, simulation=self.simulation):
            stats["aadhaar_total"] += 1
            stats["aadhaar_valid"] += int(valid)
            add(Indicator("aadhaar", self._h("aadhaar", num), "XXXX XXXX " + num[-4:], valid, True))
        for num in india.mobile_candidates(text, simulation=self.simulation):
            stats["mobile_total"] += 1
            add(Indicator("mobile_in", self._h("mobile", num), "+91 XXXXXX" + num[-4:], True, True))
        for m in india.PAN_RE.finditer(text):
            pan = m.group(1)
            add(Indicator("pan", self._h("pan", pan), f"XXXXX{pan[5:9]}X ({india.PAN_HOLDER_TYPES.get(pan[3], '?')})",
                          True, True))
        for m in india.GSTIN_RE.finditer(text):
            add(Indicator("gstin", m.group(1), m.group(1), india.gstin_valid(m.group(1))))
        for m in india.IFSC_RE.finditer(text):
            add(Indicator("ifsc", m.group(1), m.group(1), True))
        for m in india.UPI_RE.finditer(text):
            handle = f"{m.group(1)}@{m.group(2)}".lower()
            add(Indicator("upi", self._h("upi", handle), f"{handle[:3]}***@{m.group(2).lower()}", True, True))
        return list(found.values()), stats
