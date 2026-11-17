"""Phone pushes wait for the deep lane: a fast-lane CRITICAL that the deep lane downgrades never pages anyone."""
import asyncio
import json

from libertas import db
from libertas.config import Settings
from libertas.lex.audit import AuditLog
from libertas.vigiles.alerts import Vigiles
from libertas.vigiles.bus import Bus


def _setup(tmp_path):
    conn = db.connect(tmp_path / "p.db")
    audit = AuditLog(conn)
    vig = Vigiles(conn, audit, Bus(), Settings(telegram_bot_token="test-token", telegram_chat_id="1"))
    sent = []

    async def fake_telegram(payload):
        sent.append(payload["severity"])

    vig._telegram = fake_telegram
    conn.execute("INSERT INTO sources(id, name, simulated) VALUES ('s', 'Sim', 1)")
    for item_id in (1, 2):
        conn.execute("INSERT INTO items(id, source_id, item_key, title, first_seen) VALUES (?, 's', ?, 't', 'x')",
                     (item_id, f"k{item_id}"))
        conn.execute("INSERT INTO alerts(id, item_id, source_id, severity, score, title, factors_json, provisional) "
                     "VALUES (?, ?, 's', 'CRITICAL', 91, 't', '{}', 1)", (item_id, item_id))
    return conn, audit, vig, sent


def _deep(severity, score, verdict):
    return {"severity": severity, "score": score, "reasons": ["r"], "factors": {}, "authenticity": {"verdict": verdict},
            "assessed_at": "now", "title": "t"}


def test_downgraded_alert_is_not_pushed_and_confirmed_one_is(tmp_path):
    conn, audit, vig, sent = _setup(tmp_path)

    async def scenario():
        async def deep_later(item_id, deep):
            await asyncio.sleep(0.6)
            vig.update_deep(item_id, deep)
        await asyncio.gather(vig._push_when_settled(1, wait_s=5), deep_later(1, _deep("MEDIUM", 57.4, "recycled")),
                             vig._push_when_settled(2, wait_s=5), deep_later(2, _deep("CRITICAL", 91.9, "likely_genuine")))

    asyncio.run(scenario())
    assert sent == ["CRITICAL"]
    suppressed = [json.loads(r[0]) for r in conn.execute(
        "SELECT detail_json FROM audit_log WHERE action='push_suppressed'")]
    assert len(suppressed) == 1 and audit.verify()["ok"]
