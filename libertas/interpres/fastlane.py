"""The fast lane (blueprint §10): seconds from capture to an explainable, provisional assessment.

No large models are loaded here. Everything is deterministic, so the same input always gives the same score.
Every factor is returned, so an officer can see exactly why an alert is CRITICAL.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..common.timeutil import now, parse_iso
from .classify import classify, parse_scale
from .indicators import Extractor, Indicator
from .normalize import normalize
from .watchlist import Watchlist

SECTOR_CRITICALITY = {"healthcare": 1.0, "government": 1.0, "critical_infrastructure": 1.0, "banking": 0.95,
                      "telecom": 0.9, "education": 0.75, "corporate": 0.6}
SENSITIVE_KINDS = {"aadhaar": 1.0, "pan": 0.95, "mobile_in": 0.8, "upi": 0.85, "email": 0.7}
METHOD = "fastlane-rules@1"


@dataclass
class Assessment:
    method: str
    categories: list[dict]
    orgs: list[dict]
    sectors: list[str]
    indicators: list[Indicator]
    stats: dict
    scale: dict
    score: float
    severity: str
    factors: dict
    reasons: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        d = asdict(self)
        d["indicators"] = [i.as_dict() for i in self.indicators]
        return d


def severity_band(score: float) -> str:
    return "CRITICAL" if score >= 75 else "HIGH" if score >= 60 else "MEDIUM" if score >= 40 else "LOW"


def assess(title: str, body: str, *, kind: str, extra: dict, posted_at: str | None, watchlist: Watchlist,
           extractor: Extractor) -> Assessment:
    text = f"{title}\n{body}\n" + " ".join(f"{k} {v}" for k, v in (extra or {}).items() if isinstance(v, str))
    norm = normalize(text)
    indicators, stats = extractor.extract(text)
    orgs = watchlist.match(text)
    keyword_sectors = watchlist.sectors(text)
    if (extra or {}).get("sector"):
        keyword_sectors = list(dict.fromkeys([str(extra["sector"]).lower()] + keyword_sectors))
    categories = classify(norm, kind)
    scale = parse_scale(norm)
    reasons: list[str] = []

    # sector criticality: a named watchlisted organisation beats a keyword guess
    if orgs:
        sector_f = max(SECTOR_CRITICALITY.get(o["sector"], 0.6) for o in orgs)
        reasons.append("watchlisted organisation: " + ", ".join(sorted({o["org"] for o in orgs})))
    elif keyword_sectors:
        sector_f = 0.9 * max(SECTOR_CRITICALITY.get(s, 0.6) for s in keyword_sectors)
        reasons.append("sector keywords: " + ", ".join(keyword_sectors))
    else:
        sector_f = 0.4

    kinds = {i.kind for i in indicators}
    sensitivity = max([SENSITIVE_KINDS[k] for k in kinds if k in SENSITIVE_KINDS] + [0.6])
    top = categories[0]["category"] if categories else ""
    if top == "access_sale":
        sensitivity = max(sensitivity, 0.9)
    if top == "credentials_logs":
        sensitivity = max(sensitivity, 0.8)

    india_hits = watchlist.india_signals(text)
    india_f = 1.0 if any(o.get("state") for o in orgs) else 0.8 if (india_hits or kinds & {"aadhaar", "mobile_in", "upi", "pan"}) else 0.3

    credibility = 0.6
    if stats["aadhaar_total"]:
        rate = stats["aadhaar_valid"] / stats["aadhaar_total"]
        stats["aadhaar_valid_rate"] = round(rate, 2)
        if rate >= 0.9:
            credibility = 0.85
            reasons.append(f"sample identifiers pass checksums ({stats['aadhaar_valid']}/{stats['aadhaar_total']})")
        elif rate < 0.5:
            credibility = 0.25
            reasons.append(f"sample identifiers FAIL checksums ({stats['aadhaar_valid']}/{stats['aadhaar_total']}): "
                           "possibly fake or recycled")

    base = 0.30 * sector_f + 0.20 * sensitivity + 0.15 * scale["factor"] + 0.20 * india_f + 0.15 * credibility
    if categories:
        c = categories[0]
        cat_f = c["weight"] * (0.6 + 0.4 * c["confidence"])
        reasons.insert(0, f"{c['label']} (confidence {c['confidence']:.2f}; matched: {', '.join(c['matched'][:6])})")
    else:
        cat_f = 0.35
    if credibility < 0.3:
        cat_f *= 0.75
    score = round(100 * base * cat_f, 1)

    posted = parse_iso(posted_at)
    age_h = round((now() - posted).total_seconds() / 3600, 1) if posted else None
    factors = {"sector": round(sector_f, 2), "sensitivity": round(sensitivity, 2), "scale": scale["factor"],
               "india_relevance": india_f, "credibility": credibility, "category": round(cat_f, 2),
               "age_hours": age_h}
    if scale["records"]:
        reasons.append(f"claimed scale: {scale['records']:,} records")
    elif scale["size_gb"]:
        reasons.append(f"claimed size: {scale['size_gb']:g} GB")
    return Assessment(METHOD, categories, orgs, keyword_sectors, indicators, stats, scale, score,
                      severity_band(score), factors, reasons)
