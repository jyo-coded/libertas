"""M4 'done when': a new alias is linked to its known persona with evidence, the wallet cluster connects listings,
and the deep lane confirms or downgrades provisional alerts with explanations."""
import asyncio
import json

from shadownet.world import (PERSONAS, preset_fake_leak, preset_proof_paste, preset_recycled_leak,
                             preset_telecom_leak)

from .harness import Env


def _deep(env, item_id):
    r = env.conn.execute("SELECT * FROM deep_assessments WHERE item_id=?", (item_id,)).fetchone()
    assert r, f"no deep assessment for item {item_id}"
    return {k: (json.loads(r[k]) if k.endswith("_json") else r[k]) for k in r.keys()}


def test_deep_lane_end_to_end(tmp_path):
    env = Env(tmp_path)

    async def scenario():
        await env.sweep()
        preset_telecom_leak(env.store)
        preset_fake_leak(env.store)
        preset_recycled_leak(env.store)
        await env.sweep()
        preset_proof_paste(env.store)
        await env.sweep()
        ids = [r[0] for r in env.conn.execute("SELECT item_id FROM assessments")]
        return await env.deep.process(ids)

    summary = asyncio.run(scenario())
    assert summary["actors"] >= 4 and summary["chain_txs"] > 20

    # --- the live leak: genuine, attributed, money traced ---
    telecom = env.item("n1ghtcr4wl")
    d = _deep(env, telecom["id"])
    assert d["authenticity_json"]["verdict"] == "likely_genuine"
    actor = d["attribution_json"]["actor"]
    aliases = {m["alias"] for m in actor["members"]}
    assert {"n1ghtcr4wl", "cybo_kaal", "KaalDataHouse"} <= aliases
    best = d["attribution_json"]["links"][0]
    assert best["truth"] == "T3" and best["probability"] >= 0.95
    assert {"operational", "money"} <= {e["family"] for e in best["evidence"]}
    w1 = PERSONAS["P1"].wallets[1]
    exposure = d["money_json"][w1]["exposure"][0]
    assert "SimEx" in exposure["entity"] and exposure["btc"] == 0.08
    corr = d["correlation_json"]
    assert corr["wallet_links"] and "Mullai Telecom" in corr["escalation"]["new_targets"]
    alert = env.conn.execute("SELECT * FROM alerts WHERE item_id=?", (telecom["id"],)).fetchone()
    assert alert["provisional"] == 0 and alert["severity"] == "CRITICAL"
    assert any("Attribution lead (T3)" in r for r in d["reasons_json"])

    # --- the fake leak is downgraded, the recycled leak is caught ---
    fake = _deep(env, env.item("data_baniya", "%Marutham%")["id"])
    assert fake["authenticity_json"]["verdict"] == "likely_fake" and fake["severity"] != "CRITICAL"
    recycled = _deep(env, env.item("data_baniya", "%Palai Water Board Consumer Database%")["id"])
    assert recycled["authenticity_json"]["verdict"] == "recycled"
    assert "relabelled" in recycled["authenticity_json"]["reasons"][0]
    assert recycled["severity"] in ("MEDIUM", "LOW")

    # --- the proof paste is recognised as the same dataset spreading ---
    paste = env.conn.execute("SELECT id FROM items WHERE author='anon_k' AND title='Mullai Telecom proof'").fetchone()
    pd = _deep(env, paste["id"])
    assert pd["authenticity_json"]["signals"]["propagation_of"] == telecom["id"]
    paste_alert = env.conn.execute("SELECT * FROM alerts WHERE item_id=?", (paste["id"],)).fetchone()
    assert paste_alert and paste_alert["title"].startswith("Leak propagation") and paste_alert["severity"] == "HIGH"

    # --- personas stay apart ---
    alias = {r["id"]: r["alias"] for r in env.conn.execute("SELECT id, alias FROM accounts")}
    strong_pairs = {frozenset((alias[r["a"]], alias[r["b"]])) for r in env.conn.execute(
        "SELECT a, b FROM account_links WHERE probability >= 0.8")}
    assert frozenset(("cybo_kaal", "KaalDataHouse")) in strong_pairs
    assert frozenset(("data_baniya", "TrustedSeller_IN")) in strong_pairs
    assert frozenset(("volk_access", "VolkAccess")) in strong_pairs
    assert frozenset(("bhai_logs", "LogsKing")) in strong_pairs
    for a, b in [("cybo_kaal", "data_baniya"), ("cybo_kaal", "volk_access"), ("data_baniya", "bhai_logs")]:
        assert frozenset((a, b)) not in strong_pairs

    # --- graph: an explainable path from the new post to the old alias, and incidents ---
    steps = env.nexus.evidence_path(f"item:{telecom['id']}", f"account:{env.account_id('cybo_kaal')}")
    assert steps and steps[-1]["to"] == f"account:{env.account_id('cybo_kaal')}"
    assert env.conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] >= 1
    assert env.audit.verify()["ok"]
