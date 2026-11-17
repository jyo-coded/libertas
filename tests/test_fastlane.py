"""Fast-lane assessments on ShadowNet-style posts: right category, right organisation, explainable severity."""
import random

import pytest

from libertas.config import DATA
from libertas.interpres.fastlane import assess
from libertas.interpres.indicators import Extractor
from libertas.interpres.watchlist import Watchlist
from shadownet.world import ORGS, PERSONAS, access_sale, db_sale, logs_sale


@pytest.fixture(scope="module")
def ctx():
    return Watchlist.load(DATA / "watchlist.json"), Extractor(b"test-secret", simulation=True)


def run(ctx, title, body, kind="forum_thread", extra=None):
    wl, ex = ctx
    return assess(title, body, kind=kind, extra=extra or {}, posted_at=None, watchlist=wl, extractor=ex)


def test_genuine_telecom_leak_is_critical(ctx):
    title, body = db_sale(random.Random(1), PERSONAS["P1"], ORGS["mullai"], 12_000_000, 4500)
    a = run(ctx, title, body)
    assert a.severity == "CRITICAL", a.factors
    assert a.categories[0]["category"] == "data_leak_sale"
    assert a.orgs[0]["org"] == "Mullai Telecom"
    assert a.stats["aadhaar_valid_rate"] == 1.0
    kinds = {i.kind for i in a.indicators}
    assert {"wallet_btc", "tox_id", "aadhaar", "mobile_in"} <= kinds
    assert all(i.sensitive and "XXXX" in i.display for i in a.indicators if i.kind == "aadhaar")


def test_fake_leak_is_downgraded_and_explained(ctx):
    r = random.Random(2)
    real = run(ctx, *db_sale(r, PERSONAS["P2"], ORGS["marutham"], 5_000_000, 3000, valid=True))
    fake = run(ctx, *db_sale(r, PERSONAS["P2"], ORGS["marutham"], 5_000_000, 3000, valid=False))
    assert fake.score < real.score
    assert fake.factors["credibility"] < 0.3
    assert any("FAIL checksums" in reason for reason in fake.reasons)


def test_access_sale_and_logs(ctx):
    a = run(ctx, *access_sale(random.Random(3), PERSONAS["P3"], "healthcare", 120, 2400, "VPN + RDP", "domain admin", 9))
    assert a.categories[0]["category"] == "access_sale" and a.severity in ("HIGH", "CRITICAL")
    l = run(ctx, *logs_sale(random.Random(4), PERSONAS["P4"], 18, 40, ORGS["mullai"], ORGS["marutham"]))
    assert l.categories[0]["category"] == "credentials_logs"
    assert {o["org"] for o in l.orgs} == {"Mullai Telecom", "Marutham Co-operative Bank"}


def test_noise_is_low(ctx):
    a = run(ctx, "new mirror for sona bazaar?", "anyone got the new mirror for sona bazaar? old one is down")
    assert a.severity == "LOW" and not a.categories


def test_obfuscated_org_names_still_match(ctx):
    a = run(ctx, "fresh db", "selling Mu11ai Tеlеc0m sub​scriber dump 5 lakh records, price $900")
    assert a.orgs and a.orgs[0]["org"] == "Mullai Telecom" and a.orgs[0]["via"] == "deobfuscated"


def test_leak_victim_is_ransomware_claim(ctx):
    a = run(ctx, "Neithal University", "IN · education · 96 GB\nCOUNTDOWN\nWe have exfiltrated 96 GB of internal data. "
            "If Neithal University does not contact us before the deadline, everything will be published.",
            kind="leak_victim", extra={"sector": "education", "status": "countdown"})
    assert a.categories[0]["category"] == "ransomware_claim" and a.orgs[0]["org"] == "Neithal University"
