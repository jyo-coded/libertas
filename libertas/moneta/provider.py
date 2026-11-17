"""Chain data provider speaking the Esplora REST API (Blockstream/mempool.space style).

Phase 0 points at ShadowChain (simulated, localhost). In production, point it at a SELF-HOSTED Esplora/electrs
node: querying a public explorer tells its operator which addresses police are interested in (an OPSEC leak).
"""
from __future__ import annotations

import httpx


class EsploraProvider:
    def __init__(self, base_url: str, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 20.0):
        self.base = base_url.rstrip("/")
        kwargs: dict = {"timeout": timeout, "trust_env": False, "headers": {"User-Agent": "Libertas-Moneta/0.1"}}
        if transport is not None:
            kwargs["transport"] = transport
        self.client = httpx.AsyncClient(**kwargs)
        self.requests = 0

    async def address_txs(self, address: str) -> list[dict]:
        self.requests += 1
        r = await self.client.get(f"{self.base}/address/{address}/txs")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()

    async def tx(self, txid: str) -> dict | None:
        self.requests += 1
        r = await self.client.get(f"{self.base}/tx/{txid}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self.client.aclose()
