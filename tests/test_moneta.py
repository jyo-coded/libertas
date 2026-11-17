"""Moneta heuristics on the scripted ShadowChain ledger, where the ground truth is known."""
from libertas.moneta.analysis import analyse, summarise
from shadownet.chain import build_ledger
from shadownet.world import PERSONAS


def test_bitcoin_heuristics_recover_the_scripted_truth():
    ledger = build_ledger()
    an = analyse(ledger.txs, {l["address"]: l for l in ledger.labels})
    w0, w1 = PERSONAS["P1"].wallets
    s0, s1 = summarise(w0, an), summarise(w1, an)
    # common-input ownership ties the old alias's wallet to the new alias's wallet
    assert s0["cluster_id"] == s1["cluster_id"] and w1 in s0["strong_members"]
    # cash-out (0.05) + three peel-chain payments (0.01 each) all land at SimEx deposits
    assert len(s0["exposure"]) == 1 and "SimEx" in s0["exposure"][0]["entity"]
    assert s0["exposure"][0]["sats"] == 8_000_000 and len(s0["exposure"][0]["deposits"]) == 4
    assert any(f.startswith("peel chain: 4 hops") for f in s0["flags"])
    # buyers are never merged into the seller's cluster
    assert not any(ledger.roles.get(a) == "buyer" for a in s0["members"])
    # other personas stay separate
    p2 = summarise(PERSONAS["P2"].wallets[0], an)
    assert p2["cluster_id"] != s0["cluster_id"] and p2["exposure"][0]["sats"] == 6_000_000
    # the CoinJoin is flagged and clustering does NOT merge across it
    p3w = PERSONAS["P3"].wallets[0]
    p3 = summarise(p3w, an)
    assert any("coinjoin" in f for f in p3["flags"]) and p3["strong_members"] == [p3w]
    assert all("heuristic" in s["note"] for s in (s0, p2, p3))
