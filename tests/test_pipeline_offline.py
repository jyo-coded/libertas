"""End-to-end without Tor: the real pipeline against the real ShadowNet apps through an in-memory transport."""
import asyncio

import httpx

from libertas import db
from libertas.common.onion import random_v3_label
from libertas.config import DATA, Settings
from libertas.interpres.indicators import Extractor
from libertas.interpres.watchlist import Watchlist
from libertas.janus.quarantine import Quarantine
from libertas.lex.audit import AuditLog
from libertas.lex.policy import Lex
from libertas.pipeline import Pipeline
from libertas.speculatores.adapters import ADAPTERS, ItemRef
from libertas.speculatores.aquila import Source
from libertas.speculatores.fetcher import WatchSession
from libertas.vigiles.alerts import Vigiles
from libertas.vigiles.bus import Bus
from shadownet.sites import SITE_APPS
from shadownet.store import Store
from shadownet.world import preset_delete_latest, preset_telecom_leak, seed

ADAPTER_FOR = {"forum": "shadownet_forum", "market": "shadownet_market", "leakblog": "shadownet_leakblog",
               "paste": "shadownet_paste"}


class HostRouter(httpx.AsyncBaseTransport):
    def __init__(self, apps):
        self.routes = {host: httpx.ASGITransport(app=app) for host, app in apps.items()}

    async def handle_async_request(self, request):
        return await self.routes[request.url.host].handle_async_request(request)


def test_end_to_end_offline(tmp_path):
    store = Store(tmp_path / "sn.db")
    seed(store)
    labels = {k: random_v3_label() for k in ADAPTER_FOR}
    transport = HostRouter({f"{labels[k]}.onion": SITE_APPS[k](store) for k in labels})
    conn = db.connect(tmp_path / "l.db")
    audit = AuditLog(conn)
    lex = Lex(audit, mode="development", kill_file=tmp_path / "KILL", allowlist=set(labels.values()))
    bus = Bus()
    pipe = Pipeline(conn, audit, Quarantine(tmp_path / "q"), Watchlist.load(DATA / "watchlist.json"),
                    {True: Extractor(b"k", simulation=True), False: Extractor(b"k")}, Vigiles(conn, audit, bus, Settings()), bus)
    sources = [Source(f"src-{k}", k, k, labels[k], ADAPTER_FOR[k]) for k in labels]
    for s in sources:
        conn.execute("INSERT INTO sources(id, name, kind, onion, adapter, simulated) VALUES (?,?,?,?,?,1)",
                     (s.id, s.name, s.kind, s.onion, s.adapter))
    sessions = {s.id: WatchSession(s.id, Settings(), lex, transport=transport) for s in sources}

    async def fetch_detail(s, ref):
        res = await sessions[s.id].get(ref.url)
        sha = pipe.record_capture(s.id, res, "detail")
        content = ADAPTERS[s.adapter].parse_detail(s.base, ref, res)
        if content is None:
            pipe.mark_deleted(s, ref, sha)
        else:
            pipe.on_content(s, ref, content, sha)

    async def sweep():
        for s in sources:
            adapter = ADAPTERS[s.adapter]
            res = await sessions[s.id].get(adapter.pulse_url(s.base))
            assert res.ok, (s.id, res.refused, res.error, res.status)
            pipe.record_capture(s.id, res, "pulse")
            for ref in pipe.triage(s, adapter.parse_pulse(s.base, res), complete=adapter.pulse_is_complete):
                await fetch_detail(s, ref)

    asyncio.run(sweep())
    assert conn.execute("SELECT COUNT(*) FROM alerts WHERE status='new'").fetchone()[0] == 0, "backfill must not page"
    assert conn.execute("SELECT COUNT(*) FROM alerts WHERE status='historical'").fetchone()[0] >= 5

    preset_telecom_leak(store)
    asyncio.run(sweep())
    alert = conn.execute("SELECT * FROM alerts WHERE status='new'").fetchone()
    assert alert and alert["severity"] == "CRITICAL" and "Mullai Telecom" in alert["title"]
    item = conn.execute("SELECT * FROM items WHERE id=?", (alert["item_id"],)).fetchone()
    assert item["author"] == "n1ghtcr4wl" and item["detection_lag_s"] is not None and item["first_capture_sha"]
    kinds = {r[0] for r in conn.execute("SELECT kind FROM indicators WHERE item_id=?", (item["id"],))}
    assert {"wallet_btc", "tox_id", "aadhaar"} <= kinds
    assert all(r[0].startswith("XXXX") for r in conn.execute(
        "SELECT display FROM indicators WHERE item_id=? AND kind='aadhaar'", (item["id"],)))

    preset_delete_latest(store)
    src = next(s for s in sources if s.id == item["source_id"])
    # the pulse no longer lists the thread; the revisit of its detail page finds the 404
    asyncio.run(fetch_detail(src, ItemRef(item["item_key"], item["url"], item["kind"])))
    gone = conn.execute("SELECT deleted_at, first_capture_sha FROM items WHERE id=?", (item["id"],)).fetchone()
    assert gone["deleted_at"] and gone["first_capture_sha"] == item["first_capture_sha"]
    assert conn.execute("SELECT deleted FROM alerts WHERE id=?", (alert["id"],)).fetchone()[0] == 1
    assert audit.verify()["ok"]
