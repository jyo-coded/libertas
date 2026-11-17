"""Leak authenticity scoring (blueprint #17). Uses only hashed identifiers and the sample's structure; raw
personal data is never needed.

Verdicts:
  likely_genuine  checksums pass, structure and geography consistent
  recycled        the sample's identifiers already appeared in an earlier post that named a DIFFERENT organisation,
                  or old data is being sold as "fresh"
  likely_fake     identifiers fail their checksums
  unverifiable    not enough sample data to judge
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

from ..common.timeutil import parse_iso

TN_PLACES = {
    "chennai", "madurai", "coimbatore", "tiruchirappalli", "trichy", "salem", "tirunelveli", "vellore", "erode",
    "thanjavur", "thoothukudi", "tuticorin", "nagapattinam", "ramanathapuram", "kanchipuram", "tiruvallur",
    "cuddalore", "dindigul", "karur", "namakkal", "krishnagiri", "dharmapuri", "villupuram", "tiruvannamalai",
    "sivaganga", "virudhunagar", "theni", "pudukkottai", "ariyalur", "perambalur", "nilgiris", "ooty",
    "kanyakumari", "nagercoil", "tiruppur", "hosur", "kumbakonam", "pollachi", "karaikudi", "chengalpattu",
    "ranipet", "tenkasi", "kallakurichi", "mayiladuthurai", "tirupathur",
}
SENSITIVE_KINDS = ("aadhaar", "mobile_in", "email", "upi", "pan")
FRESH_CLAIM = re.compile(r"\b(fresh|new|latest|this week|not resold|recently extracted)\b", re.I)


def sample_rows(text: str) -> list[list[str]]:
    rows = []
    for line in (text or "").splitlines():
        if line.count("|") >= 2:
            cells = [c.strip() for c in line.split("|")]
            if any(ch.isdigit() for ch in line):  # skip the header row
                rows.append(cells)
    return rows


def assess_authenticity(conn: sqlite3.Connection, item_id: int) -> dict:
    item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    a = conn.execute("SELECT * FROM assessments WHERE item_id=?", (item_id,)).fetchone()
    if not item or not a:
        return {"verdict": "unverifiable", "score": 0.5, "signals": {}, "reasons": ["not yet assessed"]}
    factors = json.loads(a["factors_json"] or "{}")
    stats = factors.get("stats", {})
    orgs = {o["org"] for o in json.loads(a["orgs_json"] or "[]")}
    states = {o.get("state") for o in json.loads(a["orgs_json"] or "[]") if o.get("state")}
    rows = sample_rows(item["body_text"])
    sensitive = conn.execute(f"SELECT COUNT(*) FROM indicators WHERE item_id=? AND kind IN {SENSITIVE_KINDS}",
                             (item_id,)).fetchone()[0]
    if not rows and not sensitive:
        return {"verdict": "unverifiable", "score": 0.5, "signals": {}, "reasons": ["no sample data to test"]}

    signals: dict = {}
    reasons: list[str] = []
    parts: list[tuple[float, float]] = []  # (weight, value)
    if stats.get("aadhaar_total"):
        rate = stats["aadhaar_valid"] / stats["aadhaar_total"]
        signals["checksum_rate"] = round(rate, 2)
        parts.append((0.45, rate))
        reasons.append(f"Aadhaar checksums: {stats['aadhaar_valid']}/{stats['aadhaar_total']} valid")
    if rows:
        widths = Counter(len(r) for r in rows)
        consistency = widths.most_common(1)[0][1] / len(rows)
        signals["structure"] = round(consistency, 2)
        parts.append((0.15, consistency))
        if "Tamil Nadu" in states:
            tn = sum(1 for r in rows if any(c.lower() in TN_PLACES for c in r)) / len(rows)
            signals["geography_tn"] = round(tn, 2)
            parts.append((0.20, tn))
            reasons.append(f"sample locations in Tamil Nadu: {tn:.0%}")
    prior = conn.execute("SELECT COUNT(*) FROM items WHERE source_id=? AND author=? AND first_seen < ? AND id != ?",
                         (item["source_id"], item["author"], item["first_seen"], item_id)).fetchone()[0]
    signals["seller_prior_items"] = prior
    parts.append((0.20, min(1.0, prior / 3)))
    score = sum(w * v for w, v in parts) / sum(w for w, _ in parts) if parts else 0.5

    verdict = "likely_genuine" if score >= 0.7 else "unverifiable"
    if signals.get("checksum_rate", 1.0) < 0.5:
        verdict = "likely_fake"
        reasons.insert(0, "most sample identifiers fail their checksums: fabricated or corrupted data")

    if sensitive:
        overlaps = conn.execute(
            f"SELECT b.item_id AS other, COUNT(*) AS n FROM indicators a JOIN indicators b ON a.kind=b.kind "
            f"AND a.value=b.value AND b.item_id != a.item_id JOIN items i2 ON i2.id=b.item_id WHERE a.item_id=? "
            f"AND a.kind IN {SENSITIVE_KINDS} AND i2.first_seen < ? GROUP BY b.item_id ORDER BY n DESC",
            (item_id, item["first_seen"])).fetchall()
        if overlaps:
            top = overlaps[0]
            frac = top["n"] / sensitive
            prev = conn.execute("SELECT i.id, i.title, i.first_seen, i.source_id, a.orgs_json FROM items i "
                                "LEFT JOIN assessments a ON a.item_id=i.id WHERE i.id=?", (top["other"],)).fetchone()
            prev_orgs = {o["org"] for o in json.loads(prev["orgs_json"] or "[]")}
            age_days = None
            t_prev, t_now = parse_iso(prev["first_seen"]), parse_iso(item["first_seen"])
            if t_prev and t_now:
                age_days = round((t_now - t_prev).total_seconds() / 86400, 1)
            signals["overlap"] = {"item_id": prev["id"], "title": prev["title"], "fraction": round(frac, 2),
                                  "earlier_orgs": sorted(prev_orgs), "first_seen": prev["first_seen"],
                                  "age_days": age_days}
            if frac >= 0.5:
                relabelled = bool(orgs) and bool(prev_orgs) and not (orgs & prev_orgs)
                stale = bool(orgs & prev_orgs) and (age_days or 0) > 7 and bool(FRESH_CLAIM.search(item["body_text"] or ""))
                if relabelled:
                    verdict = "recycled"
                    score = min(score, 0.2)
                    reasons.insert(0, f"{top['n']}/{sensitive} sample identifiers already appeared in item #{prev['id']} "
                                      f"('{prev['title'][:60]}'), which named {', '.join(sorted(prev_orgs))}: "
                                      "old data relabelled as a new victim")
                elif stale:
                    verdict = "recycled"
                    score = min(score, 0.3)
                    reasons.insert(0, f"sample matches item #{prev['id']} first seen {age_days} days ago, but the "
                                      "post claims the data is fresh: old leak resold")
                else:
                    signals["propagation_of"] = prev["id"]
                    reasons.append(f"same dataset as item #{prev['id']} ('{prev['title'][:60]}'): the leak is spreading")
    if prior:
        reasons.append(f"seller has {prior} earlier post(s) on this source")
    else:
        reasons.append("seller account has no earlier posts on this source")
    return {"verdict": verdict, "score": round(score, 2), "signals": signals, "reasons": reasons}
