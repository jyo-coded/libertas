"""ShadowChain: a simulated, regtest-style Bitcoin ledger behind a subset of the Esplora REST API.

Libertas's Moneta speaks Esplora, so the same code can later point at a self-hosted Esplora/electrs node.
The ledger is deterministic and scripted to contain the patterns real investigators meet:
  * buyers paying sellers' public wallets
  * P1 spending from BOTH of its wallets in one transaction (common-input ownership links the old alias's
    wallet to the new alias's wallet)
  * a cash-out with a round payment plus change to a fresh address
  * a peel chain of small round payments to exchange deposit addresses
  * a CoinJoin (equal-value outputs) that clustering must NOT merge across
  * an exchange ("SimEx", a simulated FIU-IND registered VASP) sweeping customer deposits into its hot wallet
Every address and transaction here is fictional.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .world import PERSONAS, sim_btc

SAT = 100_000_000
EPOCH = datetime(2026, 10, 1, tzinfo=timezone.utc)


class Ledger:
    def __init__(self) -> None:
        self.txs: dict[str, dict] = {}
        self.order: list[str] = []
        self.utxos: dict[tuple[str, int], tuple[str, int]] = {}
        self.by_addr: dict[str, list[str]] = {}
        self.height = 100
        self.time = EPOCH
        self.labels: list[dict] = []
        self.notes: dict[str, str] = {}
        self.roles: dict[str, str] = {}

    @staticmethod
    def _out(addr: str, value: int) -> dict:
        return {"scriptpubkey_address": addr, "scriptpubkey_type": "v0_p2wpkh", "value": int(value)}

    def _index(self, addr: str, txid: str) -> None:
        lst = self.by_addr.setdefault(addr, [])
        if not lst or lst[-1] != txid:
            lst.append(txid)

    def _commit(self, vin: list[dict], vout: list[dict], note: str) -> str:
        self.height += 1
        self.time += timedelta(hours=7)
        body = json.dumps({"vin": vin, "vout": vout, "h": self.height}, sort_keys=True)
        txid = hashlib.sha256(hashlib.sha256(body.encode()).digest()).hexdigest()
        coinbase = bool(vin and vin[0].get("is_coinbase"))
        fee = 0 if coinbase else sum(i["prevout"]["value"] for i in vin) - sum(o["value"] for o in vout)
        self.txs[txid] = {"txid": txid, "version": 2, "locktime": 0, "vin": vin, "vout": vout, "fee": fee,
                          "status": {"confirmed": True, "block_height": self.height,
                                     "block_time": int(self.time.timestamp())}}
        self.order.append(txid)
        self.notes[txid] = note
        for i in vin:
            if not i.get("is_coinbase"):
                self._index(i["prevout"]["scriptpubkey_address"], txid)
                del self.utxos[(i["txid"], i["vout"])]
        for n, o in enumerate(vout):
            self._index(o["scriptpubkey_address"], txid)
            self.utxos[(txid, n)] = (o["scriptpubkey_address"], o["value"])
        return txid

    def mint(self, outputs: list[tuple[str, int]], note: str = "funding") -> str:
        vin = [{"txid": "0" * 64, "vout": 4294967295, "prevout": None, "is_coinbase": True, "sequence": 4294967295}]
        return self._commit(vin, [self._out(a, v) for a, v in outputs], note)

    def spend(self, from_addrs: list[str], outputs: list[tuple[str, int]], change: str | None = None,
              fee: int = 2_000, note: str = "", select_all: bool = False) -> str:
        need = sum(v for _, v in outputs) + fee
        picked, total = [], 0
        for key, (addr, value) in sorted(self.utxos.items(), key=lambda kv: (-kv[1][1], kv[0])):
            if addr in from_addrs:
                picked.append((key, addr, value))
                total += value
                if total >= need and not select_all:
                    break
        if total < need:
            raise ValueError(f"insufficient funds for '{note}': have {total}, need {need}")
        vin = [{"txid": k[0], "vout": k[1], "prevout": self._out(a, v), "is_coinbase": False, "sequence": 4294967293}
               for k, a, v in picked]
        vout = [self._out(a, v) for a, v in outputs]
        if total - need:
            if change is None:
                raise ValueError(f"'{note}' needs a change address")
            vout.append(self._out(change, total - need))
        return self._commit(vin, vout, note)

    def coinjoin(self, participants: list[str], denomination: int, fresh, fee_each: int = 1_000) -> str:
        vin, vout = [], []
        for addr in participants:
            key, (a, value) = max(((k, v) for k, v in self.utxos.items() if v[0] == addr), key=lambda kv: kv[1][1])
            vin.append({"txid": key[0], "vout": key[1], "prevout": self._out(a, value), "is_coinbase": False,
                        "sequence": 4294967293})
            vout.append(self._out(fresh(), denomination))
            leftover = value - denomination - fee_each
            if leftover > 0:
                vout.append(self._out(fresh(), leftover))
        return self._commit(vin, vout, "CoinJoin (equal-value outputs)")

    # ---------- Esplora-style views ----------
    def address_txs(self, addr: str) -> list[dict]:
        return [self.txs[t] for t in reversed(self.by_addr.get(addr, []))]

    def address_stats(self, addr: str) -> dict:
        funded = [(t, o) for t in self.by_addr.get(addr, []) for o in self.txs[t]["vout"] if o["scriptpubkey_address"] == addr]
        spent = [(t, i) for t in self.by_addr.get(addr, []) for i in self.txs[t]["vin"]
                 if not i.get("is_coinbase") and i["prevout"]["scriptpubkey_address"] == addr]
        return {"address": addr, "chain_stats": {
            "funded_txo_count": len(funded), "funded_txo_sum": sum(o["value"] for _, o in funded),
            "spent_txo_count": len(spent), "spent_txo_sum": sum(i["prevout"]["value"] for _, i in spent),
            "tx_count": len(self.by_addr.get(addr, []))}}


def build_ledger() -> Ledger:
    r = random.Random(777)
    L = Ledger()

    def fresh() -> str:
        return sim_btc(r)

    P = PERSONAS
    p1w0, p1w1 = P["P1"].wallets
    p2w, p3w, p4w = P["P2"].wallets[0], P["P3"].wallets[0], P["P4"].wallets[0]
    hot = fresh()
    deposits = [fresh() for _ in range(8)]
    buyers = [fresh() for _ in range(14)]
    cj_others = [fresh() for _ in range(4)]
    L.roles.update({hot: "SimEx hot wallet", **{d: "SimEx deposit" for d in deposits},
                    **{b: "buyer" for b in buyers}, p1w0: "P1 public wallet", p1w1: "P1 second wallet"})

    L.mint([(b, r.randint(8, 40) * 1_000_000) for b in buyers] + [(c, 3_000_000) for c in cj_others], "buyers funded")
    for i in range(4):  # buyers pay cybo_kaal / KaalDataHouse
        L.spend([buyers[i]], [(p1w0, r.randint(20, 45) * 100_000 + r.randint(0, 99_999))], change=fresh(),
                note="buyer pays P1 public wallet")
    for i in range(4, 6):  # buyers pay the wallet the new alias will use
        L.spend([buyers[i]], [(p1w1, r.randint(15, 30) * 100_000 + r.randint(0, 99_999))], change=fresh(),
                note="buyer pays P1 second wallet")
    sweep = fresh()
    L.spend([p1w0, p1w1], [], change=sweep, select_all=True, note="P1 consolidates both wallets (common input)")
    change = fresh()
    L.spend([sweep], [(deposits[0], 5_000_000)], change=change, note="P1 cash-out to SimEx with change")
    cur = change
    for k in range(1, 4):
        nxt = fresh()
        L.spend([cur], [(deposits[k], 1_000_000)], change=nxt, note=f"P1 peel chain step {k}")
        cur = nxt
    for i in range(6, 9):  # TrustedSeller_IN / data_baniya
        L.spend([buyers[i]], [(p2w, r.randint(25, 60) * 100_000 + r.randint(0, 99_999))], change=fresh(),
                note="buyer pays P2")
    L.spend([p2w], [(deposits[4], 6_000_000)], change=fresh(), note="P2 cash-out to SimEx with change")
    for i in range(9, 11):  # volk_access / VolkAccess
        L.spend([buyers[i]], [(p3w, r.randint(30, 80) * 100_000)], change=fresh(), note="buyer pays P3")
    L.coinjoin([p3w] + cj_others, 2_000_000, fresh)
    for i in range(11, 14):  # bhai_logs / LogsKing
        L.spend([buyers[i]], [(p4w, r.randint(3, 9) * 100_000 + r.randint(0, 99_999))], change=fresh(),
                note="buyer pays P4")
    L.spend(deposits[:5], [], change=hot, select_all=True, note="SimEx sweeps customer deposits into its hot wallet")
    L.labels = [{"address": hot, "entity": "SimEx Exchange (simulated FIU-IND registered VASP)", "type": "exchange",
                 "source": "analyst label (simulation)"}]
    return L


def chain_app(ledger: Ledger) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/")
    def index():
        return HTMLResponse("<h1>ShadowChain</h1><p>SIMULATED regtest-style Bitcoin ledger for the Libertas demo. "
                            f"{len(ledger.txs)} transactions. Esplora-compatible API under /api.</p>")

    @app.get("/api/address/{addr}")
    def address(addr: str):
        return ledger.address_stats(addr)

    @app.get("/api/address/{addr}/txs")
    def address_txs(addr: str):
        return ledger.address_txs(addr)[:50]

    @app.get("/api/tx/{txid}")
    def tx(txid: str):
        if txid not in ledger.txs:
            raise HTTPException(404, "Transaction not found")
        return ledger.txs[txid]

    return app
