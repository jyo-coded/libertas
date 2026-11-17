"""ShadowNet renders correctly and only ever produces synthetic, never-issued identifiers."""
import re

import pytest
from fastapi.testclient import TestClient

from libertas.interpres.cryptoaddr import btc_bech32_info, find_wallets
from libertas.interpres.india import aadhaar_candidates, verhoeff_valid
from libertas.janus.sanitize import parse_html, parse_xml
from shadownet.sites import forum_app, leakblog_app, market_app, paste_app
from shadownet.store import Store
from shadownet.world import PERSONAS, PRESETS, seed


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    s = Store(tmp_path_factory.mktemp("sn") / "sn.db")
    counts = seed(s)
    assert counts["threads"] >= 20 and counts["victims"] == 5
    return s


def test_forum_pages_and_rss(store):
    c = TestClient(forum_app(store))
    assert c.get("/").status_code == 200
    rss = c.get("/syndication.php", headers={"host": "x.onion"})
    assert rss.headers["content-type"].startswith("application/rss+xml")
    items = parse_xml(rss.content).findall("./channel/item")
    assert len(items) == 20 and items[0].find("link").text.startswith("http://x.onion/showthread.php?tid=")
    tid = int(items[0].find("guid").text.split("-")[1])
    page = c.get(f"/showthread.php?tid={tid}")
    doc = parse_html(page.content, "http://x.onion/")
    assert page.status_code == 200 and "SIMULATION" in doc.text
    assert any(l.hidden and l.url.endswith("/admin/trap") for l in doc.links)
    store.delete_thread(tid)
    assert c.get(f"/showthread.php?tid={tid}").status_code == 404


def test_market_leakblog_paste(store):
    m = TestClient(market_app(store))
    assert m.get("/").status_code == 200 and m.get("/listing/1").status_code == 200
    lb = TestClient(leakblog_app(store))
    data = lb.get("/api/victims.json").json()
    assert data["simulation"] and len(data["victims"]) == 5
    p = TestClient(paste_app(store))
    pid = store.pastes()[0]["id"]
    raw = p.get(f"/raw/{pid}")
    assert raw.status_code == 200 and raw.headers["content-type"].startswith("text/plain")


def test_identifiers_are_synthetic(store):
    text = "\n".join(p["body"] for t in store.threads(limit=100) for p in store.thread_posts(t["tid"]))
    found = aadhaar_candidates(text, simulation=True)
    assert found, "seed should contain Aadhaar-format samples"
    assert all(num.startswith("1") for num, _ in found), "synthetic Aadhaar numbers must start with 1 (never issued)"
    assert all(valid for _, valid in found)
    assert not any(valid for _, valid in aadhaar_candidates(text, simulation=False))
    mobiles = re.findall(r"\+91 (\d)", text)
    assert mobiles and set(mobiles) == {"5"}
    for w in find_wallets(text):
        if w["chain"] == "BTC":
            assert w["valid"] and w["info"]["network"] == "regtest"
    for p in PERSONAS.values():
        assert btc_bech32_info(p.wallets[0])["network"] == "regtest"


def test_presets_run(store):
    for key, (_, fn) in PRESETS.items():
        assert isinstance(fn(store), str)
