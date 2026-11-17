"""Organisation watchlist matcher (blueprint #13). Matches survive homoglyphs, leetspeak and odd spacing."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .normalize import deleet_variants, normalize

SECTOR_KEYWORDS = {
    "healthcare": ["hospital", "healthcare", "patient", "medical", "clinic", "health trust", "lab reports"],
    "telecom": ["telecom", "subscriber", "mobile operator", "isp", "sim card"],
    "banking": ["bank", "banking", "nbfc", "fintech", "credit card", "net banking"],
    "government": ["government", "gov.in", "nic.in", "ministry", "municipal", "water board", "sarkari", "panchayat"],
    "education": ["university", "college", "school", "student", "exam results"],
    "critical_infrastructure": ["power grid", "electricity", "scada", "water supply", "railway", "port authority"],
}
INDIA_TERMS = ["india", "indian", "aadhaar", "pan card", "upi", "lakh", "crore", "rs.", "₹", "tamil nadu", "chennai",
               "madurai", "coimbatore", "+91", "kyc"]


def _term_pattern(term: str) -> str:
    words = [re.escape(w) for w in normalize(term).split()]
    return r"(?<![a-z0-9])" + r"[\s\-_.]*".join(words) + r"(?![a-z0-9])"


class Watchlist:
    def __init__(self, entries: list[dict]):
        self.entries = []
        for e in entries:
            pats = [_term_pattern(t) for t in e.get("terms", [])] + [_term_pattern(d) for d in e.get("domains", [])]
            self.entries.append({**e, "regex": re.compile("|".join(pats)) if pats else None})
        self._sector_res = {s: re.compile("|".join(_term_pattern(k) for k in kws)) for s, kws in SECTOR_KEYWORDS.items()}
        self._india_re = re.compile("|".join(re.escape(t) for t in INDIA_TERMS))

    @classmethod
    def load(cls, path: Path) -> "Watchlist":
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["organisations"])

    def match(self, text: str) -> list[dict]:
        norm = normalize(text)
        variants = deleet_variants(norm)
        hits = []
        for e in self.entries:
            if not e["regex"]:
                continue
            m = e["regex"].search(norm)
            via = "exact"
            if not m:
                via = "deobfuscated"
                for variant in variants:
                    m = e["regex"].search(variant)
                    if m:
                        break
            if m:
                hits.append({"org": e["org"], "sector": e["sector"], "state": e.get("state", ""),
                             "city": e.get("city", ""), "matched": m.group(0).strip(), "via": via})
        return hits

    def sectors(self, text: str) -> list[str]:
        norm = normalize(text)
        return [s for s, rx in self._sector_res.items() if rx.search(norm)]

    def india_signals(self, text: str) -> int:
        return len(set(self._india_re.findall(normalize(text))))
