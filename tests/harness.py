"""Offline harness: the real Libertas pipeline and deep lane against the real ShadowNet apps and ShadowChain,
connected through in-memory transports (no Tor, no network)."""
from __future__ import annotations

import httpx

from libertas import db
from libertas.common.onion import random_v3_label
from libertas.config import DATA, Settings
from libertas.deeplane import DeepLane
from libertas.interpres.indicators import Extractor
from libertas.interpres.watchlist import Watchlist
from libertas.janus.quarantine import Quarantine
from libertas.lex.audit import AuditLog
from libertas.lex.policy import Lex
from libertas.moneta import EsploraProvider, Moneta
from libertas.nexus import Nexus
from libertas.pipeline import Pipeline
from libertas.speculatores.adapters import ADAPTERS
from libertas.speculatores.aquila import Source
from libertas.speculatores.fetcher import WatchSession
from libertas.stilus import Stilus
from libertas.vigiles.alerts import Vigiles
from libertas.vigiles.bus import Bus
from shadownet.chain import build_ledger, chain_app
from shadownet.sites import SITE_APPS
from shadownet.store import Store
from shadownet.world import seed

ADAPTER_FOR = {"forum": "shadownet_forum", "market": "shadownet_market", "leakblog": "shadownet_leakblog",
               "paste": "shadownet_paste"}


class HostRouter(httpx.AsyncBaseTransport):
    def __init__(self, apps):
        self.routes = {host: httpx.ASGITransport(app=app) for host, app in apps.items()}

    async def handle_async_request(self, request):
        return await self.routes[request.url.host].handle_async_request(request)


class Env:
    def __init__(self, tmp_path):
        self.store = Store(tmp_path / "sn.db")
        seed(self.store)
        labels = {k: random_v3_label() for k in ADAPTER_FOR}
        transport = HostRouter({f"{labels[k]}.onion": SITE_APPS[k](self.store) for k in labels})
        self.conn = db.connect(tmp_path / "l.db")
        self.audit = AuditLog(self.conn)
        self.lex = Lex(self.audit, mode="development", kill_file=tmp_path / "KILL", allowlist=set(labels.values()))
        self.bus = Bus()
        self.vigiles = Vigiles(self.conn, self.audit, self.bus, Settings())
        self.pipe = Pipeline(self.conn, self.audit, Quarantine(tmp_path / "q"), Watchlist.load(DATA / "watchlist.json"),
                             {True: Extractor(b"k", simulation=True), False: Extractor(b"k")}, self.vigiles, self.bus)
        self.sources = [Source(f"src-{k}", k, k, labels[k], ADAPTER_FOR[k]) for k in labels]
        for s in self.sources:
            self.conn.execute("INSERT INTO sources(id, name, kind, onion, adapter, simulated) VALUES (?,?,?,?,?,1)",
                              (s.id, s.name, s.kind, s.onion, s.adapter))
        self.sessions = {s.id: WatchSession(s.id, Settings(), self.lex, transport=transport) for s in self.sources}
        self.ledger = build_ledger()
        self.provider = EsploraProvider("http://chain.local/api",
                                        transport=httpx.ASGITransport(app=chain_app(self.ledger)))
        self.moneta = Moneta(self.conn, self.provider, self.ledger.labels)
        self.stilus, self.nexus = Stilus(self.conn), Nexus(self.conn)
        self.deep = DeepLane(self.conn, self.audit, self.bus, self.vigiles, self.stilus, self.moneta, self.nexus,
                             log=lambda m: None)

    async def fetch_detail(self, s, ref):
        res = await self.sessions[s.id].get(ref.url)
        sha = self.pipe.record_capture(s.id, res, "detail")
        content = ADAPTERS[s.adapter].parse_detail(s.base, ref, res)
        if content is None:
            self.pipe.mark_deleted(s, ref, sha)
        else:
            self.pipe.on_content(s, ref, content, sha)

    async def sweep(self):
        for s in self.sources:
            adapter = ADAPTERS[s.adapter]
            res = await self.sessions[s.id].get(adapter.pulse_url(s.base))
            assert res.ok, (s.id, res.refused, res.error, res.status)
            self.pipe.record_capture(s.id, res, "pulse")
            for ref in self.pipe.triage(s, adapter.parse_pulse(s.base, res), complete=adapter.pulse_is_complete):
                await self.fetch_detail(s, ref)

    def item(self, author: str, title_like: str = "%"):
        return self.conn.execute("SELECT * FROM items WHERE author=? AND title LIKE ? ORDER BY id DESC LIMIT 1",
                                 (author, title_like)).fetchone()

    def account_id(self, alias: str) -> int:
        return self.conn.execute("SELECT id FROM accounts WHERE alias=?", (alias,)).fetchone()[0]
