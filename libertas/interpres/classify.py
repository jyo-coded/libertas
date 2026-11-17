"""Rule-based threat classification and scale parsing for the fast lane (method "rules@1").

Fast, transparent and explainable: every category lists the terms that triggered it. The deep lane (M4) adds
learned models on top; these rules stay as the always-on baseline.
"""
from __future__ import annotations

import math
import re

CATEGORIES = {
    "data_leak_sale": {"label": "Data leak / database sale", "weight": 1.0, "sale": True, "terms": {
        "database": 2, "db": 2, "dump": 2, "leak": 2, "leaked": 2, "records": 2, "rows": 1.5, "lines": 1,
        "fullz": 2, "sample": 1, "fresh": 1, "not resold": 1.5, "customer": 1, "subscriber": 1, "patient": 1.5,
        "aadhaar": 1.5, "data": 1}},
    "ransomware_claim": {"label": "Ransomware / extortion claim", "weight": 1.0, "sale": False, "terms": {
        "exfiltrated": 3, "will be published": 3, "deadline": 2, "ransom": 3, "countdown": 2,
        "refused to cooperate": 2, "published below": 2, "contact us before": 2}},
    "access_sale": {"label": "Initial access sale", "weight": 1.0, "sale": True, "terms": {
        "access": 1.5, "rdp": 2.5, "vpn": 2, "citrix": 2.5, "webshell": 2.5, "domain admin": 3, "domain user": 2,
        "local admin": 2, "revenue": 1.5, "privileges": 2, "initial access": 3}},
    "credentials_logs": {"label": "Stealer logs / credentials", "weight": 0.9, "sale": True, "terms": {
        "logs": 2, "stealer": 3, "combo": 2.5, "logins": 2, "credentials": 2, "cookies": 1.5, "password": 1}},
    "fraud_infrastructure": {"label": "Fraud infrastructure (mule accounts, SIMs)", "weight": 0.9, "sale": True,
                             "terms": {"current account": 3, "current accounts": 3, "savings accounts": 2,
                                       "kyc done": 3, "kyc is fully done": 3, "for rent": 2.5, "monthly rent": 2.5,
                                       "mule": 3, "net banking": 2, "upi": 1.5, "sim card": 2}},
    "carding": {"label": "Carding", "weight": 0.8, "sale": True, "terms": {
        "cvv": 3, "bins": 2, "dumps with pin": 3}},
    "malware_exploit": {"label": "Malware / exploit trade", "weight": 0.8, "sale": True, "terms": {
        "exploit": 2.5, "0day": 3, "zero-day": 3, "loader": 2, "crypter": 3, "ransomware builder": 3}},
}
SALE_TERMS = ["price", "selling", "btc", "usdt", "xmr", "escrow", "rs.", "₹", "$", "dm ", "contact", "buy",
              "per account", "per 1k"]
_compiled = {cat: [(t, w, re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])")) for t, w in spec["terms"].items()]
             for cat, spec in CATEGORIES.items()}


def classify(norm: str, kind: str = "") -> list[dict]:
    is_sale = any(t in norm for t in SALE_TERMS)
    results = []
    for cat, spec in CATEGORIES.items():
        matched = [t for t, _, rx in _compiled[cat] if rx.search(norm)]
        score = sum(spec["terms"][t] for t in matched)
        if cat == "ransomware_claim" and kind == "leak_victim":
            score += 4
            matched.append("(leak-site listing)")
        if spec["sale"] and not is_sale:
            score *= 0.6
        conf = round(min(0.95, score / 8), 2)
        if conf >= 0.3:
            results.append({"category": cat, "label": spec["label"], "confidence": conf, "matched": matched,
                            "weight": spec["weight"]})
    return sorted(results, key=lambda r: r["confidence"] * r["weight"], reverse=True)


_MULT = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "million": 1e6, "mn": 1e6, "m": 1e6,
         "k": 1e3, "thousand": 1e3, "billion": 1e9, "bn": 1e9}
_NUM = r"(\d{1,3}(?:[ ,]\d{3})+|\d+(?:\.\d+)?)"
_COUNT_RE = re.compile(_NUM + r"\s*(crore|cr|lakhs?|lac|million|mn|m|k|thousand|billion|bn)?\s*"
                       r"(?:\w+\s+){0,2}?(records|rows|lines|users|customers|patients|subscribers|entries|accounts|logs)\b")
_LOGS_K_RE = re.compile(r"(\d+(?:\.\d+)?)\s*k\b[^\n.]{0,30}\blogs\b")
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|tb|mb)\b")


def parse_scale(norm: str) -> dict:
    records = 0.0
    for m in _COUNT_RE.finditer(norm):
        number = float(m.group(1).replace(" ", "").replace(",", ""))
        records = max(records, number * _MULT.get(m.group(2) or "", 1))
    for m in _LOGS_K_RE.finditer(norm):
        records = max(records, float(m.group(1)) * 1e3)
    size_gb = 0.0
    for m in _SIZE_RE.finditer(norm):
        size_gb = max(size_gb, float(m.group(1)) * {"mb": 0.001, "gb": 1, "tb": 1000}[m.group(2)])
    if records:
        factor = min(1.0, math.log10(max(records, 10)) / 8)
    elif size_gb:
        factor = min(1.0, math.log10(max(size_gb * 1000, 10)) / 6)
    else:
        factor = 0.3
    return {"records": int(records), "size_gb": size_gb, "factor": round(factor, 3)}
