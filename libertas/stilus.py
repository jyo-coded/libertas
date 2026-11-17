"""Stilus: who is behind an alias (blueprint §13.2). Produces investigative LEADS with evidence, never verdicts.

Three independent evidence families are fused with a noisy-OR:
  operational  the same PGP / Tox / Session / Jabber / Telegram identifier or wallet used by two accounts (T1 facts)
  stylometry   character n-grams, function words and writing habits, scored RELATIVE to all other account pairs
               (a robust z-score), and capped at 0.85 so style alone can never "prove" identity (T2)
  money        two accounts' wallets fall in the same Moneta cluster (heuristic, T2)
Two or more families agreeing gives a corroborated (T3) link.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import statistics
from collections import Counter
from itertools import combinations

from .common.timeutil import now_iso

OPERATIONAL_WEIGHTS = {"pgp_fingerprint": 0.97, "tox_id": 0.95, "session_id": 0.95, "jabber": 0.9, "telegram": 0.85,
                       "wallet_btc": 0.9, "wallet_eth": 0.9, "wallet_tron": 0.9, "wallet_xmr": 0.9}
GENERIC_ALIASES = {"", "anonymous", "anon", "guest", "unknown", "admin"}
MIN_STYLE_CHARS = 200
STYLE_CAP = 0.85
LINK_KEEP = 0.35
ACTOR_THRESHOLD = 0.8
FUNCTION_WORDS = ["the", "a", "an", "of", "to", "in", "for", "on", "with", "and", "or", "but", "is", "are", "was",
                  "be", "it", "this", "that", "we", "i", "you", "my", "our", "your", "not", "no", "only", "just",
                  "all", "from", "have", "has", "any", "per", "so", "if", "before", "after", "now", "will", "can"]
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9]{20,}\b")
_WORD = re.compile(r"[a-z']+")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
MARKERS = {
    "hinglish": re.compile(r"\b(bhai|hai|ka|ke|ki|karo|sab|sirf|jaldi|dekho|ekdum|milega|wale|bhi)\b"),
    "formal": re.compile(r"\b(kindly|revert|needful|sir|madam|regards|dear|genuine)\b"),
    "slang": re.compile(r"\b(bro|af|dm|pls|lol|tho|ngl)\b"),
    "terse": re.compile(r"\b(only|no test|no free|escrow)\b"),
}


def clean_for_style(text: str) -> str:
    """Drop data (sample rows, combo lines, IDs, addresses); keep the author's own words."""
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.count("|") >= 2 or re.fullmatch(r"\S+@\S+:\S+", s):
            continue
        if sum(ch.isalpha() for ch in s) < 0.4 * len(s):
            continue
        s = _LONG_TOKEN.sub(" ", s)
        out.append(re.sub(r"\d", "9", s))
    return "\n".join(out)


def char_ngrams(text: str, lo: int = 2, hi: int = 4) -> Counter:
    t = " ".join(text.lower().split())
    c: Counter = Counter()
    for n in range(lo, hi + 1):
        c.update(t[i:i + n] for i in range(len(t) - n + 1))
    return c


def tfidf(docs: dict) -> dict:
    n = len(docs)
    df: Counter = Counter()
    for c in docs.values():
        df.update(c.keys())
    vecs = {}
    for key, c in docs.items():
        v = {g: (1 + math.log(cnt)) * (math.log((1 + n) / (1 + df[g])) + 1) for g, cnt in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs[key] = {g: x / norm for g, x in v.items()}
    return vecs


def cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(g, 0.0) for g, x in a.items())


def function_profile(text: str) -> dict:
    words = _WORD.findall(text.lower())
    total = max(1, len(words))
    c = Counter(w for w in words if w in FUNCTION_WORDS)
    v = {w: c[w] / total for w in FUNCTION_WORDS if c[w]}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {w: x / norm for w, x in v.items()}


def markers(text: str) -> dict:
    letters = [ch for ch in text if ch.isalpha()]
    lines = [l for l in text.splitlines() if l.strip()]
    words = max(1, len(_WORD.findall(text.lower())))
    low = text.lower()
    m = {"lowercase": sum(ch.islower() for ch in letters) / max(1, len(letters)),
         "emoji": min(1.0, len(_EMOJI.findall(text)) / max(1, len(lines))),
         "exclaim": min(1.0, text.count("!") / max(1, len(lines))),
         "line_len": min(1.0, (sum(len(l) for l in lines) / max(1, len(lines))) / 120),
         "tilde_signoff": 1.0 if re.search(r"(^|\n)~\w", text) else 0.0,
         "arrow": min(1.0, text.count("->") / max(1, len(lines)))}
    for name, rx in MARKERS.items():
        m[name] = min(1.0, 8 * len(rx.findall(low)) / words)
    return m


def marker_similarity(a: dict, b: dict) -> float:
    return 1 - sum(abs(a[k] - b[k]) for k in a) / len(a)


def _word_ngrams(text: str) -> set:
    w = _WORD.findall(text.lower())
    return {" ".join(w[i:i + n]) for n in (2, 3) for i in range(len(w) - n + 1)}


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def groups(self) -> list[set]:
        out: dict = {}
        for x in self.parent:
            out.setdefault(self.find(x), set()).add(x)
        return list(out.values())


class Stilus:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ---------- accounts ----------
    def sync_accounts(self) -> dict[int, dict]:
        rows = self.conn.execute(
            "SELECT source_id, author, MIN(first_seen) AS fs, MAX(first_seen) AS ls, COUNT(*) AS n FROM items "
            "WHERE author IS NOT NULL AND author != '' GROUP BY source_id, author").fetchall()
        for r in rows:
            if r["author"].strip().lower() in GENERIC_ALIASES:
                continue
            self.conn.execute(
                "INSERT INTO accounts(source_id, alias, first_seen, last_seen, items) VALUES (?,?,?,?,?) "
                "ON CONFLICT(source_id, alias) DO UPDATE SET last_seen=excluded.last_seen, items=excluded.items",
                (r["source_id"], r["author"], r["fs"], r["ls"], r["n"]))
        accounts = {}
        for a in self.conn.execute("SELECT a.*, s.name AS source_name FROM accounts a JOIN sources s ON s.id=a.source_id"):
            texts = [f"{t['title'] or ''}\n{t['body_text'] or ''}" for t in self.conn.execute(
                "SELECT title, body_text FROM items WHERE source_id=? AND author=?", (a["source_id"], a["alias"]))]
            accounts[a["id"]] = {"id": a["id"], "alias": a["alias"], "source_id": a["source_id"],
                                 "source_name": a["source_name"], "items": a["items"],
                                 "style_text": clean_for_style("\n".join(texts))}
        return accounts

    # ---------- evidence families ----------
    def operational(self, accounts: dict) -> dict:
        kinds = tuple(OPERATIONAL_WEIGHTS)
        rows = self.conn.execute(
            f"SELECT ind.kind, ind.value, ind.display, ind.item_id, ac.id AS account_id FROM indicators ind "
            f"JOIN items i ON i.id=ind.item_id JOIN accounts ac ON ac.source_id=i.source_id AND ac.alias=i.author "
            f"WHERE ind.kind IN {kinds}").fetchall()
        by_value: dict = {}
        for r in rows:
            by_value.setdefault((r["kind"], r["value"]), {"display": r["display"], "accounts": {}})
            by_value[(r["kind"], r["value"])]["accounts"].setdefault(r["account_id"], []).append(r["item_id"])
        pairs: dict = {}
        for (kind, _value), info in by_value.items():
            accs = sorted(a for a in info["accounts"] if a in accounts)
            for a, b in combinations(accs, 2):
                pairs.setdefault((a, b), []).append(
                    {"family": "operational", "kind": kind, "display": info["display"], "weight": OPERATIONAL_WEIGHTS[kind],
                     "items": sorted(set(info["accounts"][a] + info["accounts"][b]))})
        return pairs

    def stylometry(self, accounts: dict) -> dict:
        usable = {k: v for k, v in accounts.items() if len(v["style_text"]) >= MIN_STYLE_CHARS}
        if len(usable) < 2:
            return {}
        vecs = tfidf({k: char_ngrams(v["style_text"]) for k, v in usable.items()})
        fw = {k: function_profile(v["style_text"]) for k, v in usable.items()}
        mk = {k: markers(v["style_text"]) for k, v in usable.items()}
        grams = {k: _word_ngrams(v["style_text"]) for k, v in usable.items()}
        gram_df: Counter = Counter()
        for g in grams.values():
            gram_df.update(g)
        sims = {}
        for a, b in combinations(sorted(usable), 2):
            sims[(a, b)] = 0.6 * cosine(vecs[a], vecs[b]) + 0.25 * cosine(fw[a], fw[b]) + 0.15 * marker_similarity(mk[a], mk[b])
        values = list(sims.values())
        med = statistics.median(values)
        mad = statistics.median(abs(v - med) for v in values) * 1.4826 or (statistics.pstdev(values) or 0.05)
        out = {}
        for (a, b), s in sims.items():
            z = (s - med) / mad
            length = min(1.0, min(len(usable[a]["style_text"]), len(usable[b]["style_text"])) / 600)
            p = STYLE_CAP / (1 + math.exp(-1.6 * (z - 2.0))) * length
            shared = sorted((g for g in grams[a] & grams[b] if gram_df[g] <= 2), key=len, reverse=True)[:6]
            out[(a, b)] = {"family": "stylometry", "similarity": round(s, 3), "z": round(z, 2), "p": round(p, 3),
                           "distinctive_shared_phrases": shared}
        return out

    # ---------- fusion ----------
    def recompute(self, money_pairs: dict | None = None) -> dict:
        accounts = self.sync_accounts()
        ops = self.operational(accounts)
        style = self.stylometry(accounts)
        money = money_pairs or {}
        ts = now_iso()
        links = []
        for pair in set(ops) | set(style) | set(money):
            a, b = pair
            evidence = []
            kinds_seen: dict = {}
            for e in ops.get(pair, []):
                kinds_seen[e["kind"]] = max(kinds_seen.get(e["kind"], 0), e["weight"])
                evidence.append(e)
            p_ops = 1 - math.prod(1 - w for w in kinds_seen.values()) if kinds_seen else 0.0
            p_style = style.get(pair, {}).get("p", 0.0)
            if pair in style and p_style >= 0.05:
                evidence.append(style[pair])
            p_money = money.get(pair, {}).get("p", 0.0)
            if pair in money:
                evidence.append(money[pair])
            prob = 1 - (1 - p_ops) * (1 - p_style) * (1 - p_money)
            families = sum(1 for p in (p_ops, p_style, p_money) if p >= 0.3)
            truth = "T3" if families >= 2 else ("T1" if p_ops >= 0.85 else "T2")
            if prob >= LINK_KEEP:
                links.append({"a": a, "b": b, "probability": round(prob, 3), "truth": truth, "evidence": evidence,
                              "families": families})
        self.conn.execute("DELETE FROM account_links")
        self.conn.executemany("INSERT INTO account_links(a, b, probability, truth, evidence_json, updated_at) VALUES (?,?,?,?,?,?)",
                              [(l["a"], l["b"], l["probability"], l["truth"], json.dumps(l["evidence"]), ts) for l in links])
        actors = self._actors(accounts, links, ts)
        return {"accounts": accounts, "links": links, "actors": actors}

    def _actors(self, accounts: dict, links: list[dict], ts: str) -> list[dict]:
        uf = UnionFind()
        for acc in accounts:
            uf.find(acc)
        strong = [l for l in links if l["probability"] >= ACTOR_THRESHOLD]
        for l in strong:
            uf.union(l["a"], l["b"])
        self.conn.execute("UPDATE accounts SET actor_id=NULL")
        actors = []
        for group in uf.groups():
            if len(group) < 2:
                continue
            members = sorted(group)
            anchor = f"account:{members[0]}"
            label = max(members, key=lambda m: (accounts[m]["items"], -m))
            member_best = {m: max((l["probability"] for l in strong if m in (l["a"], l["b"])), default=0) for m in members}
            truths = {l["truth"] for l in strong if l["a"] in group and l["b"] in group}
            truth = "T3" if "T3" in truths else ("T1" if "T1" in truths else "T2")
            member_json = json.dumps([{"account_id": m, "alias": accounts[m]["alias"], "source": accounts[m]["source_name"],
                                       "best_link": round(member_best[m], 3)} for m in members])
            self.conn.execute(
                "INSERT INTO actors(anchor, label, members_json, confidence, truth, created_at, updated_at) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(anchor) DO UPDATE SET label=excluded.label, members_json=excluded.members_json, "
                "confidence=excluded.confidence, truth=excluded.truth, updated_at=excluded.updated_at",
                (anchor, accounts[label]["alias"], member_json, round(min(member_best.values()), 3), truth, ts, ts))
            actor_id = self.conn.execute("SELECT id FROM actors WHERE anchor=?", (anchor,)).fetchone()[0]
            self.conn.executemany("UPDATE accounts SET actor_id=? WHERE id=?", [(actor_id, m) for m in members])
            actors.append({"id": actor_id, "label": accounts[label]["alias"], "members": members, "truth": truth})
        live = {a["id"] for a in actors}
        for row in self.conn.execute("SELECT id FROM actors").fetchall():
            if row["id"] not in live:
                self.conn.execute("DELETE FROM actors WHERE id=?", (row["id"],))
        return actors

    # ---------- per-item view ----------
    def attribution_for_item(self, item_id: int) -> dict | None:
        r = self.conn.execute(
            "SELECT ac.id, ac.alias, ac.actor_id, s.name AS source_name FROM items i JOIN accounts ac "
            "ON ac.source_id=i.source_id AND ac.alias=i.author JOIN sources s ON s.id=i.source_id WHERE i.id=?",
            (item_id,)).fetchone()
        if not r:
            return None
        out = {"account_id": r["id"], "alias": r["alias"], "source": r["source_name"], "actor": None, "links": []}
        for l in self.conn.execute("SELECT * FROM account_links WHERE a=? OR b=? ORDER BY probability DESC", (r["id"], r["id"])):
            other = l["b"] if l["a"] == r["id"] else l["a"]
            o = self.conn.execute("SELECT ac.alias, s.name FROM accounts ac JOIN sources s ON s.id=ac.source_id WHERE ac.id=?",
                                  (other,)).fetchone()
            out["links"].append({"account_id": other, "alias": o["alias"], "source": o["name"],
                                 "probability": l["probability"], "truth": l["truth"],
                                 "evidence": json.loads(l["evidence_json"])})
        if r["actor_id"]:
            actor = self.conn.execute("SELECT * FROM actors WHERE id=?", (r["actor_id"],)).fetchone()
            members = json.loads(actor["members_json"])
            ids = [m["account_id"] for m in members]
            hist = self.conn.execute(
                f"SELECT i.id, i.title, i.first_seen, a.orgs_json FROM items i JOIN accounts ac ON ac.source_id=i.source_id "
                f"AND ac.alias=i.author LEFT JOIN assessments a ON a.item_id=i.id WHERE ac.id IN ({','.join('?' * len(ids))}) "
                f"AND i.id != ? ORDER BY i.first_seen", (*ids, item_id)).fetchall()
            orgs = sorted({o["org"] for h in hist for o in json.loads(h["orgs_json"] or "[]")})
            out["actor"] = {"id": actor["id"], "label": actor["label"], "truth": actor["truth"],
                            "confidence": actor["confidence"], "members": members, "prior_items": len(hist),
                            "prior_targets": orgs}
        return out
