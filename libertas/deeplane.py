"""The deep lane (blueprint §10): minutes-scale enrichment that never blocks the fast lane.

For each batch of new or changed items it:
  1. syncs accounts,
  2. runs Moneta (chain expansion, clustering, exposure),
  3. runs Stilus (operational + stylometry + money fusion → links and actors),
  4. runs Nexus (incidents and per-item correlation),
  5. re-scores the item and upgrades its alert from 'provisional' to 'deep-confirmed', keeping both sets of reasons.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import traceback

from .common.timeutil import now_iso
from .interpres.authenticity import assess_authenticity
from .interpres.fastlane import severity_band
from .lex.audit import AuditLog
from .nexus import Nexus
from .stilus import Stilus
from .vigiles.alerts import Vigiles
from .vigiles.bus import Bus

METHOD = "deeplane@1"
VERDICT_MULTIPLIER = {"recycled": 0.7, "likely_fake": 0.75}


def _btc(sats: int) -> str:
    return f"{sats / 1e8:.4f}"


class DeepLane:
    def __init__(self, conn: sqlite3.Connection, audit: AuditLog, bus: Bus, vigiles: Vigiles, stilus: Stilus, moneta,
                 nexus: Nexus, log=print):
        self.conn, self.audit, self.bus, self.vigiles = conn, audit, bus, vigiles
        self.stilus, self.moneta, self.nexus, self.log = stilus, moneta, nexus, log
        self.queue: asyncio.Queue = asyncio.Queue()
        self.last_pass: dict = {}

    def submit(self, item_id: int) -> None:
        self.queue.put_nowait((item_id, time.perf_counter()))

    async def run(self) -> None:
        try:
            initial = [r[0] for r in self.conn.execute(
                "SELECT item_id FROM alerts UNION SELECT DISTINCT item_id FROM indicators "
                "WHERE kind IN ('aadhaar','mobile_in','email','upi','pan')")]
            await self.process(initial, initial=True)
        except Exception:
            self.log("deep lane initial pass failed:\n" + traceback.format_exc())
        while True:
            item_id, t = await self.queue.get()
            batch = {item_id: t}
            while True:  # debounce: gather everything that arrives within a second
                try:
                    more, t2 = await asyncio.wait_for(self.queue.get(), 1.0)
                    batch.setdefault(more, t2)
                except asyncio.TimeoutError:
                    break
            try:
                await self.process(list(batch), submitted=batch)
            except Exception:
                self.log("deep lane pass failed:\n" + traceback.format_exc())

    async def process(self, item_ids: list[int], *, submitted: dict | None = None, initial: bool = False) -> dict:
        started = time.perf_counter()
        self.stilus.sync_accounts()
        money = (await self.moneta.investigate() if self.moneta
                 else {"wallets": {}, "account_pairs": {}, "xmr": {}, "tx_count": 0})
        attribution = self.stilus.recompute(money_pairs=money["account_pairs"])
        self.nexus.recompute_incidents()
        updated = 0
        for item_id in item_ids:
            deep = self.deep_assess(item_id, money)
            if not deep:
                continue
            if submitted and item_id in submitted:
                deep["latency_s"] = round(time.perf_counter() - submitted[item_id], 2)
            self._store(item_id, deep)
            if self.vigiles.update_deep(item_id, deep):
                updated += 1
        summary = {"items": len(item_ids), "updated": updated, "seconds": round(time.perf_counter() - started, 2),
                   "actors": len(attribution["actors"]), "links": len(attribution["links"]),
                   "chain_txs": money.get("tx_count", 0), "initial": initial}
        self.last_pass = {**summary, "at": now_iso()}
        self.audit.append("deeplane", "pass", f"{len(item_ids)} items", "ok", summary)
        self.bus.publish({"type": "deep_pass", **summary})
        self.log(f"deep lane: {updated}/{len(item_ids)} alerts confirmed in {summary['seconds']}s; "
                 f"{summary['actors']} actors, {summary['links']} alias links, {summary['chain_txs']} chain txs")
        return summary

    def deep_assess(self, item_id: int, money: dict) -> dict | None:
        a = self.conn.execute("SELECT * FROM assessments WHERE item_id=?", (item_id,)).fetchone()
        if not a:
            return None
        f = json.loads(a["factors_json"] or "{}")
        cats = json.loads(a["categories_json"] or "[]")
        auth = assess_authenticity(self.conn, item_id)
        attribution = self.stilus.attribution_for_item(item_id)
        wallets = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT value FROM indicators WHERE item_id=? AND kind='wallet_btc'", (item_id,))]
        money_view = {}
        for w in wallets:
            s = money["wallets"].get(w)
            if s and s.get("found"):
                money_view[w] = {k: s[k] for k in ("cluster_id", "size", "received_sats", "sent_sats", "tx_count",
                                                   "entity", "exposure", "flags", "note")}
                money_view[w]["peel_chains"] = len(s["peel_chains"])
                money_view[w]["evidence"] = s["evidence"][:6]
        xmr = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT value FROM indicators WHERE item_id=? AND kind='wallet_xmr'", (item_id,))]
        correlation = self.nexus.correlate(item_id, attribution)

        scale = f.get("scale")
        scale_f = scale["factor"] if isinstance(scale, dict) else (scale or 0.3)
        cred = auth["score"] if auth["verdict"] != "unverifiable" else f.get("credibility", 0.6)
        actor = (attribution or {}).get("actor")
        if actor and actor["prior_items"] >= 3 and auth["verdict"] not in VERDICT_MULTIPLIER:
            cred = min(1.0, cred + 0.1)
        base = (0.30 * f.get("sector", 0.4) + 0.20 * f.get("sensitivity", 0.6) + 0.15 * scale_f
                + 0.20 * f.get("india_relevance", 0.3) + 0.15 * cred)
        cat_f = cats[0]["weight"] * (0.6 + 0.4 * cats[0]["confidence"]) if cats else 0.35
        mult = VERDICT_MULTIPLIER.get(auth["verdict"], 1.0)
        score = round(100 * base * cat_f * mult, 1)

        reasons = [f"Authenticity: {auth['verdict'].replace('_', ' ')} ({auth['score']}): {auth['reasons'][0]}"]
        propagation = auth["signals"].get("propagation_of")
        if propagation:
            src = self.conn.execute("SELECT i.title, s.name FROM items i JOIN sources s ON s.id=i.source_id WHERE i.id=?",
                                    (propagation,)).fetchone()
            score = max(score, 60.0)
            reasons.insert(0, f"Leak spreading: same dataset as item #{propagation} ('{(src['title'] or '')[:60]}' on "
                              f"{src['name']}) now appears here")
        orgs = sorted({o["org"] for o in json.loads(a["orgs_json"] or "[]")})
        label = "Leak propagation" if propagation else (cats[0]["label"] if cats else "Suspicious post")
        title = f"{label} — {', '.join(orgs) or 'unattributed'}"
        if actor:
            others = [m["alias"] for m in actor["members"] if m["alias"] != attribution["alias"]]
            best = attribution["links"][0] if attribution["links"] else None
            kinds = sorted({e.get("kind") or e["family"] for e in (best["evidence"] if best else [])})
            reasons.append(f"Attribution lead ({actor['truth']}): '{attribution['alias']}' is likely run by the same "
                           f"actor as {', '.join(repr(o) for o in others)}; strongest link P={best['probability'] if best else '?'} "
                           f"via {', '.join(kinds)}; actor has {actor['prior_items']} earlier posts")
        elif attribution and attribution["links"]:
            l = attribution["links"][0]
            reasons.append(f"Possible link ({l['truth']}, P={l['probability']}) to '{l['alias']}' on {l['source']}")
        for w, m in money_view.items():
            line = f"Wallet {w[:14]}… is in cluster {m['cluster_id']} ({m['size']} addresses)"
            if m["exposure"]:
                e = m["exposure"][0]
                line += f"; the cluster sent {e['btc']} BTC to {e['entity']} ({len(e['deposits'])} deposits): legal-notice target"
            if m["flags"]:
                line += "; " + "; ".join(m["flags"])
            reasons.append(line)
        if xmr:
            reasons.append("Monero address present: on-chain tracing not possible; off-chain intelligence only")
        for wl in correlation["wallet_links"]:
            reasons.append(f"Same wallet cluster appears in {len(wl['items'])} other post(s): "
                           + "; ".join(f"#{i['id']} by {i['author']} on {i['source']}" for i in wl["items"][:4]))
        if correlation["escalation"]:
            e = correlation["escalation"]
            reasons.append(f"Escalation: actor '{e['actor']}' has a NEW target {', '.join(e['new_targets'])} "
                           f"(earlier: {', '.join(e['previous_targets'][:5]) or 'none'})")
        if correlation["incident"]:
            inc = correlation["incident"]
            reasons.append(f"Incident: {inc['title']}")
        return {"method": METHOD, "assessed_at": now_iso(), "title": title, "authenticity": auth, "attribution": attribution,
                "money": money_view, "xmr": xmr, "correlation": correlation, "score": score,
                "severity": severity_band(score), "reasons": reasons,
                "factors": {"sector": f.get("sector"), "sensitivity": f.get("sensitivity"), "scale": scale_f,
                            "india_relevance": f.get("india_relevance"), "credibility": round(cred, 2),
                            "category": round(cat_f, 2), "authenticity_multiplier": mult}}

    def _store(self, item_id: int, deep: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO deep_assessments(item_id, assessed_at, method, authenticity_json, attribution_json, "
            "money_json, correlation_json, score, severity, reasons_json, latency_s) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, deep["assessed_at"], deep["method"], json.dumps(deep["authenticity"]),
             json.dumps(deep["attribution"]), json.dumps(deep["money"]), json.dumps(deep["correlation"]),
             deep["score"], deep["severity"], json.dumps(deep["reasons"]), deep.get("latency_s")))
