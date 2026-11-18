"""M7 resilience: ShadowNet's adversary mode against Libertas's wall handling, the heartbeat canary, deadline-aware
polling and the Lex boundary drill. Each side is tested against the other's real output, not a hand-made fixture."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from libertas import db
from libertas.lex.audit import AuditLog
from libertas.lex.drill import run as lex_drill
from libertas.lex.policy import Lex
from libertas.speculatores.adapters import ADAPTERS, ItemRef, ParseDrift
from libertas.speculatores.fetcher import FetchResult
from libertas.speculatores.heartbeat import Heartbeat, deadline_interval, nearest_deadline, parse_canary
from libertas.speculatores.walls import detect_wall
from shadownet.adversary import Adversary, heartbeat_app, install
from shadownet.sites import forum_app
from shadownet.store import Store
from shadownet.world import seed


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    s = Store(tmp_path_factory.mktemp("adv") / "sn.db")
    seed(s)
    return s


def as_fetch(resp) -> FetchResult:
    return FetchResult(url="http://x.onion/", final_url="http://x.onion/", isolation_id="t", status=resp.status_code,
                       content_type=resp.headers.get("content-type", "").split(";")[0], body=resp.content,
                       headers={k.lower(): v for k, v in resp.headers.items()})


def forum(store, adv):
    app = forum_app(store)
    install(app, "forum", adv)
    return TestClient(app)


def test_captcha_wall_is_recognised_not_mistaken_for_drift_or_deletion(store):
    adv = Adversary()
    c = forum(store, adv)
    tid = store.threads(limit=1)[0]["tid"]
    normal = as_fetch(c.get(f"/showthread.php?tid={tid}"))
    assert detect_wall(normal) is None  # a real thread page is never a wall
    adv.set("captcha", True)
    wall = detect_wall(as_fetch(c.get(f"/showthread.php?tid={tid}")))
    assert wall and wall.kind == "captcha" and "never solved" in wall.detail
    assert adv.state()["counters"]["captcha_served"] == 1
    # the RSS pulse is untouched by the wall, so new items are still seen
    assert c.get("/syndication.php").status_code == 200


def test_rate_limit_answers_429_with_retry_after(store):
    adv = Adversary()
    adv.set("ratelimit", True)
    c = forum(store, adv)
    statuses = [c.get("/").status_code for _ in range(10)]
    assert statuses[:8] == [200] * 8 and statuses[-1] == 429
    wall = detect_wall(as_fetch(c.get("/")))
    assert wall.kind == "rate_limit" and wall.cooldown_s == 20


def test_randomised_markup_raises_parse_drift_instead_of_guessing(store):
    adv = Adversary()
    c = forum(store, adv)
    tid = store.threads(limit=1)[0]["tid"]
    adapter = ADAPTERS["shadownet_forum"]
    ref = ItemRef(f"thread:{tid}", f"http://x.onion/showthread.php?tid={tid}", "forum_thread")
    assert adapter.parse_detail("http://x.onion", ref, as_fetch(c.get(f"/showthread.php?tid={tid}"))).body_text
    adv.set("randomise", True)
    with pytest.raises(ParseDrift):
        adapter.parse_detail("http://x.onion", ref, as_fetch(c.get(f"/showthread.php?tid={tid}")))


def test_a_post_about_captchas_is_not_a_wall(store):
    uid = store.member_by_name("bhai_logs")["uid"]
    tid = store.create_thread(5, "selling captcha solver api", uid, 'cheap captcha bypass <input name="captcha">',
                              datetime.now(timezone.utc).isoformat(timespec="seconds"))
    page = as_fetch(TestClient(forum_app(store)).get(f"/showthread.php?tid={tid}"))
    assert detect_wall(page) is None  # escaped text in a post can't look like a form field


def test_fast_delete_and_deadline_publication(store):
    t0 = datetime.now(timezone.utc)
    old = (t0 - timedelta(seconds=90)).isoformat(timespec="seconds")
    uid = store.member_by_name("cybo_kaal")["uid"]
    tid = store.create_thread(1, "short-lived", uid, "gone soon", old)
    found = store.created_between((t0 - timedelta(minutes=5)).isoformat(timespec="seconds"),
                                  (t0 - timedelta(seconds=60)).isoformat(timespec="seconds"))
    assert ("thread", str(tid)) in found
    store.delete_any("thread", str(tid))
    assert store.thread(tid) is None
    vid = store.create_victim("Due Corp", "IN", "health", "due.example", old, "countdown", "1 GB", "x", old)
    assert vid in store.publish_due_victims(t0.isoformat(timespec="seconds"))
    assert store.victim(vid)["status"] == "published"


def test_heartbeat_measures_detection_from_the_real_canary():
    page = TestClient(heartbeat_app()).get("/").text
    seq, published = parse_canary(page)
    hb = Heartbeat(onion="x")
    pub = datetime.fromisoformat(published).timestamp()
    assert hb.observe(page, pub + 5) is None  # the first sighting can't know when the minute started for us
    nxt = page.replace(f"seq: {seq}", f"seq: {seq + 1}").replace(published, datetime.fromtimestamp(pub + 60, timezone.utc).isoformat())
    assert hb.observe(nxt, pub + 60 + 12.5) == 12.5
    assert hb.summary()["median_lag_s"] == 12.5 and hb.state == "ok"
    hb.refresh(pub + 60 + 400)
    assert hb.state == "stale"
    assert parse_canary("hello") is None


def test_deadline_tightens_polling():
    assert deadline_interval(86_400, 20) == 20
    assert deadline_interval(1800, 20) == 12
    assert deadline_interval(300, 20) == 8
    assert deadline_interval(30, 20) == 5 and deadline_interval(-60, 20) == 5
    now = datetime.now(timezone.utc)
    rows = [(1, "far", {"status": "countdown", "deadline": (now + timedelta(hours=72)).isoformat()}),
            (2, "near", {"status": "countdown", "deadline": (now + timedelta(minutes=3)).isoformat()}),
            (3, "done", {"status": "published", "deadline": (now - timedelta(hours=1)).isoformat()})]
    assert nearest_deadline(rows, now)["item_id"] == 2


def test_lex_drill_refuses_every_attempt_and_keeps_the_chain(tmp_path):
    conn = db.connect(tmp_path / "l.db")
    audit = AuditLog(conn)
    forum_onion = "5taekob4nflzwoh4lmycml5cxm4lh6z4hpqttf5eeavx5olwbbjh3oad"
    lex = Lex(audit, mode="development", kill_file=tmp_path / "KILL", allowlist={forum_onion})
    result = lex_drill(lex, forum_onion)
    assert result["passed"] and result["refused"] == result["total"] == 6
    reasons = " | ".join(r["reason"] for r in result["attempts"])
    for expected in ("only GET", "credentials in URL", "allowlist", "clearnet", ".zip", ".exe"):
        assert expected in reasons
    assert result["audit"]["ok"]
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE action='fetch' AND decision='deny'").fetchone()[0] == 6


def test_kill_switch_severs_a_request_already_on_the_wire(tmp_path):
    import asyncio

    import httpx

    from libertas.config import Settings
    from libertas.speculatores.fetcher import WatchSession

    onion = "5taekob4nflzwoh4lmycml5cxm4lh6z4hpqttf5eeavx5olwbbjh3oad"
    conn = db.connect(tmp_path / "k.db")
    lex = Lex(AuditLog(conn), mode="development", kill_file=tmp_path / "KILL", allowlist={onion})

    async def slow(request):
        await asyncio.sleep(30)  # a slow onion: the response would arrive long after the halt
        return httpx.Response(200, text="late")

    async def scenario():
        session = WatchSession("t", Settings(), lex, transport=httpx.MockTransport(slow))
        pending = asyncio.create_task(session.get(f"http://{onion}.onion/"))
        await asyncio.sleep(0.2)
        cut = await session.sever()
        res = await asyncio.wait_for(pending, 2)
        await session.aclose()
        return cut, res

    cut, res = asyncio.run(scenario())
    assert cut == 1 and res.refused == "severed by the kill switch" and res.body is None
