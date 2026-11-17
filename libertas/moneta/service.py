"""Moneta service: expand from the wallets seen in posts, analyse, persist, and hand money evidence to Stilus."""
from __future__ import annotations

import json
import sqlite3
import time

from ..common.timeutil import now_iso
from .analysis import analyse, summarise, tx_addresses
from .provider import EsploraProvider

MONERO_NOTE = ("Monero hides sender, receiver and amount on-chain (stealth addresses, ring signatures, RingCT); the "
               "FCMP++ upgrade widens this further. Libertas tracks Monero off-chain: reuse of this address across "
               "listings, swap-service touchpoints and exchange requests.")


class Moneta:
    def __init__(self, conn: sqlite3.Connection, provider: EsploraProvider, labels: list[dict], *,
                 max_hops: int = 7, max_addresses: int = 400, ttl_s: float = 600.0):
        self.conn, self.provider = conn, provider
        self.labels = {l["address"]: l for l in labels}
        self.max_hops, self.max_addresses, self.ttl_s = max_hops, max_addresses, ttl_s
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    async def _address_txs(self, addr: str) -> list[dict]:
        hit = self._cache.get(addr)
        if hit and time.monotonic() - hit[0] < self.ttl_s:
            return hit[1]
        txs = await self.provider.address_txs(addr)
        self._cache[addr] = (time.monotonic(), txs)
        ts = now_iso()
        self.conn.executemany("INSERT OR REPLACE INTO chain_txs(txid, chain, raw_json, fetched_at) VALUES (?,?,?,?)",
                              [(t["txid"], "BTC", json.dumps(t), ts) for t in txs])
        return txs

    async def expand(self, seeds: list[str]) -> dict[str, dict]:
        txs: dict[str, dict] = {}
        seen: set[str] = set()
        frontier = list(dict.fromkeys(seeds))
        for _hop in range(self.max_hops + 1):
            nxt: list[str] = []
            for addr in frontier:
                if addr in seen or len(seen) >= self.max_addresses:
                    continue
                seen.add(addr)
                for t in await self._address_txs(addr):
                    txs[t["txid"]] = t
                    nxt.extend(a for a in tx_addresses(t) if a not in seen)
            frontier = list(dict.fromkeys(nxt))
            if not frontier:
                break
        return txs

    def _seeds(self) -> tuple[list[str], list[str]]:
        btc = [r[0] for r in self.conn.execute("SELECT DISTINCT value FROM indicators WHERE kind='wallet_btc' AND valid=1")]
        xmr = [r[0] for r in self.conn.execute("SELECT DISTINCT value FROM indicators WHERE kind='wallet_xmr'")]
        return btc, xmr

    async def investigate(self) -> dict:
        btc, xmr = self._seeds()
        started = time.perf_counter()
        summaries: dict[str, dict] = {}
        tx_count = 0
        if btc:
            txs = await self.expand(btc)
            tx_count = len(txs)
            an = analyse(txs, self.labels)
            summaries = {seed: summarise(seed, an) for seed in btc}
            self._persist(summaries)
        result = {"wallets": summaries, "xmr": {a: {"chain": "XMR", "note": MONERO_NOTE} for a in xmr},
                  "tx_count": tx_count, "seconds": round(time.perf_counter() - started, 2),
                  "requests": self.provider.requests}
        result["account_pairs"] = self._account_pairs(summaries)
        return result

    def _persist(self, summaries: dict[str, dict]) -> None:
        ts = now_iso()
        for seed, s in summaries.items():
            if not s.get("found"):
                self.conn.execute("INSERT OR REPLACE INTO wallets(address, chain, cluster_id, received_sats, sent_sats, "
                                  "tx_count, label, analysed_at) VALUES (?,?,?,?,?,?,?,?)",
                                  (seed, "BTC", None, 0, 0, 0, None, ts))
                continue
            self.conn.execute("INSERT OR REPLACE INTO wallets(address, chain, cluster_id, received_sats, sent_sats, "
                              "tx_count, label, analysed_at) VALUES (?,?,?,?,?,?,?,?)",
                              (seed, "BTC", s["cluster_id"], s["received_sats"], s["sent_sats"], s["tx_count"],
                               s["entity"], ts))
            self.conn.execute("INSERT OR REPLACE INTO wallet_clusters(id, chain, addresses_json, size, evidence_json, "
                              "flags_json, exposure_json, label, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                              (s["cluster_id"], "BTC", json.dumps(s["members"]), s["size"], json.dumps(s["evidence"]),
                               json.dumps(s["flags"] + [{"peel_chains": s["peel_chains"]}]), json.dumps(s["exposure"]),
                               s["entity"], ts))

    def _account_pairs(self, summaries: dict[str, dict]) -> dict:
        """Accounts whose DIFFERENT wallets fall in the same cluster. (The same exact wallet is an operational
        overlap, handled by Stilus directly.)"""
        rows = self.conn.execute(
            "SELECT DISTINCT ind.value AS wallet, ac.id AS account_id FROM indicators ind JOIN items i ON i.id=ind.item_id "
            "JOIN accounts ac ON ac.source_id=i.source_id AND ac.alias=i.author WHERE ind.kind='wallet_btc'").fetchall()
        by_cluster: dict[str, dict[int, set[str]]] = {}
        for r in rows:
            s = summaries.get(r["wallet"])
            if s and s.get("found"):
                by_cluster.setdefault(s["cluster_id"], {}).setdefault(r["account_id"], set()).add(r["wallet"])
        pairs: dict = {}
        for cid, accs in by_cluster.items():
            ids = sorted(accs)
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    if accs[a] & accs[b]:
                        continue
                    wa, wb = sorted(accs[a])[0], sorted(accs[b])[0]
                    sa = summaries[wa]
                    strong = wb in sa["strong_members"]
                    pairs[(a, b)] = {"family": "money", "cluster": cid, "wallets": [wa, wb],
                                     "basis": "common-input ownership" if strong else "change / consolidation heuristics",
                                     "p": 0.75 if strong else 0.6}
        return pairs
