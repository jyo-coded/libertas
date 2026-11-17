"""Bitcoin heuristics (blueprint §13.3). Pure functions over Esplora-format transactions.

Every link carries its heuristic name and a confidence. Clusters are investigative leads: heuristic clustering
does NOT prove common ownership.
"""
from __future__ import annotations

import hashlib
from collections import Counter

ROUND_UNIT = 1_000_000  # 0.01 BTC


def tx_inputs(tx: dict) -> list[str]:
    return [v["prevout"]["scriptpubkey_address"] for v in tx.get("vin", [])
            if not v.get("is_coinbase") and v.get("prevout") and v["prevout"].get("scriptpubkey_address")]


def tx_outputs(tx: dict) -> list[tuple[str, int]]:
    return [(o["scriptpubkey_address"], o["value"]) for o in tx.get("vout", []) if o.get("scriptpubkey_address")]


def tx_addresses(tx: dict) -> set[str]:
    return set(tx_inputs(tx)) | {a for a, _ in tx_outputs(tx)}


def is_coinjoin(tx: dict) -> bool:
    ins, outs = set(tx_inputs(tx)), tx_outputs(tx)
    if len(ins) < 3 or len(outs) < 3:
        return False
    return Counter(v for _, v in outs).most_common(1)[0][1] >= 3


def is_round(value: int) -> bool:
    return value > 0 and value % ROUND_UNIT == 0


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def members(self, x: str) -> set[str]:
        root = self.find(x)
        return {y for y in list(self.parent) if self.find(y) == root}


def analyse(txs: dict[str, dict], labels: dict[str, dict]) -> dict:
    ordered = sorted(txs.values(), key=lambda t: (t["status"]["block_height"], t["txid"]))
    first_out: dict[str, str] = {}
    for t in ordered:
        for a, _ in tx_outputs(t):
            first_out.setdefault(a, t["txid"])
    strong, extended = UnionFind(), UnionFind()
    links, coinjoins, steps = [], [], {}
    for t in ordered:
        txid, ins, outs = t["txid"], list(dict.fromkeys(tx_inputs(t))), tx_outputs(t)
        for a in tx_addresses(t):
            strong.find(a)
            extended.find(a)
        if not ins:
            continue
        if is_coinjoin(t):
            coinjoins.append({"txid": txid, "inputs": ins, "equal_outputs": Counter(v for _, v in outs).most_common(1)[0]})
            continue
        for a in ins[1:]:
            strong.union(ins[0], a)
            extended.union(ins[0], a)
            links.append({"a": ins[0], "b": a, "heuristic": "common-input ownership", "confidence": 0.9, "txid": txid})
        if len(outs) == 1 and len(ins) >= 2 and outs[0][0] in labels:
            # deposits swept into a labelled exchange wallet belong to that exchange
            for a in ins:
                strong.union(outs[0][0], a)
                extended.union(outs[0][0], a)
            links.append({"a": ins[0], "b": outs[0][0], "heuristic": "deposit sweep into a labelled entity wallet",
                          "confidence": 0.85, "txid": txid})
        elif len(outs) == 1 and len(ins) >= 2:
            extended.union(ins[0], outs[0][0])
            links.append({"a": ins[0], "b": outs[0][0], "heuristic": "consolidation sweep", "confidence": 0.65,
                          "txid": txid})
        if len(outs) == 2:
            best = None
            for (addr, value), (_other, other_value) in ((outs[0], outs[1]), (outs[1], outs[0])):
                if addr in labels:
                    continue
                conf, why = 0.0, []
                if addr in ins:
                    conf, why = 0.95, ["returned to an input address"]
                elif is_round(other_value) and not is_round(value):
                    conf += 0.45
                    why.append("the other output is a round amount")
                if first_out.get(addr) == txid:
                    conf += 0.25
                    why.append("fresh address")
                if best is None or conf > best[0]:
                    best = (conf, addr, why)
            if best and best[0] >= 0.5:
                extended.union(ins[0], best[1])
                links.append({"a": ins[0], "b": best[1], "heuristic": "change (" + ", ".join(best[2]) + ")",
                              "confidence": round(best[0], 2), "txid": txid})
                payment = outs[0] if outs[1][0] == best[1] else outs[1]
                if len(ins) == 1 and is_round(payment[1]):
                    steps[ins[0]] = {"txid": txid, "change": best[1], "paid_to": payment[0], "value": payment[1]}
    peel_chains = []
    change_targets = {s["change"] for s in steps.values()}
    for start in steps:
        if start in change_targets:
            continue
        chain, addr = [], start
        while addr in steps and len(chain) < 50:
            chain.append(steps[addr])
            addr = steps[addr]["change"]
        if len(chain) >= 3:
            peel_chains.append({"start": start, "steps": chain, "total_paid": sum(s["value"] for s in chain)})
    entity_addrs: dict[str, dict] = {}
    for addr, label in labels.items():
        if addr in strong.parent:
            for m in strong.members(addr):
                entity_addrs[m] = label
    return {"txs": txs, "strong": strong, "extended": extended, "links": links, "coinjoins": coinjoins,
            "peel_chains": peel_chains, "entity_addrs": entity_addrs}


def cluster_id(members: set[str]) -> str:
    return "C-" + hashlib.sha256("|".join(sorted(members)).encode()).hexdigest()[:10]


def summarise(seed: str, an: dict) -> dict:
    if seed not in an["extended"].parent:
        return {"seed": seed, "found": False, "note": "no on-chain activity found for this address"}
    members = an["extended"].members(seed)
    strong = an["strong"].members(seed)
    entity = an["entity_addrs"].get(seed)
    received = sent = 0
    tx_count = 0
    for t in an["txs"].values():
        outs, ins = tx_outputs(t), set(tx_inputs(t))
        hit = False
        for a, v in outs:
            if a == seed:
                received += v
                hit = True
        if seed in ins:
            sent += sum(o["prevout"]["value"] for o in t["vin"] if not o.get("is_coinbase") and o.get("prevout")
                        and o["prevout"]["scriptpubkey_address"] == seed)
            hit = True
        tx_count += hit
    exposure: dict[str, dict] = {}
    for t in an["txs"].values():
        if set(tx_inputs(t)) & members:
            for a, v in tx_outputs(t):
                label = an["entity_addrs"].get(a)
                if label and a not in members:
                    e = exposure.setdefault(label["entity"], {"entity": label["entity"], "type": label.get("type"),
                                                             "sats": 0, "deposits": set(), "txids": []})
                    e["sats"] += v
                    e["deposits"].add(a)
                    e["txids"].append(t["txid"])
    flags = []
    if any(set(cj["inputs"]) & members for cj in an["coinjoins"]):
        flags.append("coinjoin interaction (clustering stops at the CoinJoin)")
    chains = [c for c in an["peel_chains"] if c["start"] in members]
    if chains:
        flags.append(f"peel chain: {sum(len(c['steps']) for c in chains)} hops paying out "
                     f"{sum(c['total_paid'] for c in chains) / 1e8:.4f} BTC")
    evidence = [l for l in an["links"] if l["a"] in members and l["b"] in members][:40]
    return {"seed": seed, "found": True, "cluster_id": cluster_id(members), "size": len(members),
            "strong_members": sorted(strong), "members": sorted(members), "received_sats": received, "sent_sats": sent,
            "tx_count": tx_count, "entity": entity["entity"] if entity else None,
            "exposure": [{**e, "deposits": sorted(e["deposits"]), "btc": round(e["sats"] / 1e8, 8)}
                         for e in exposure.values()],
            "flags": flags, "peel_chains": chains, "evidence": evidence,
            "note": "heuristic clustering: an investigative lead, not proof of common ownership"}
