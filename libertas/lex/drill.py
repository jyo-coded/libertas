"""The Lex boundary drill (demo script beat 5:45): ask the crawler to cross the line and show that it can't.

Every attempt goes through Lex.check_fetch, the same gate every collector request passes before any network
traffic. Nothing here touches the network: a refused request never leaves the machine. Each refusal is written
to the hash-chained audit log, which is verified again afterwards.
"""
from __future__ import annotations

from ..common.onion import random_v3_label
from .policy import Lex

DRILL_ACTOR_SOURCE = "lex-drill"


def attempts(forum_onion: str) -> list[dict]:
    forum = f"http://{forum_onion}.onion"
    return [
        {"attempt": "Log in to Kaal Forum with a member account", "method": "POST",
         "url": f"{forum}/member.php?action=do_login"},
        {"attempt": "Sign in by putting a username and password in the address", "method": "GET",
         "url": f"http://moderator:hunter2@{forum_onion}.onion/modcp.php"},
        {"attempt": "Reach an onion that is not authorised for collection", "method": "GET",
         "url": f"http://{random_v3_label()}.onion/"},
        {"attempt": "Leave Tor and fetch from the open internet", "method": "GET",
         "url": "https://pastebin.com/raw/leak"},
        {"attempt": "Download the leaked database archive", "method": "GET",
         "url": f"{forum}/attachments/mullai_full_dump.zip"},
        {"attempt": "Run an executable a seller attached", "method": "GET",
         "url": f"{forum}/attachments/checker.exe"},
    ]


def run(lex: Lex, forum_onion: str, actor: str = "operator") -> dict:
    lex.audit.append(actor, "lex_drill", "boundary", "started", {"attempts": len(attempts(forum_onion))})
    rows = []
    for a in attempts(forum_onion):
        decision = lex.check_fetch(a["method"], a["url"], source_id=DRILL_ACTOR_SOURCE)
        seq = lex.audit.conn.execute("SELECT MAX(seq) FROM audit_log").fetchone()[0]
        rows.append({**a, "allowed": decision.allowed, "reason": decision.reason, "audit_seq": seq})
    verify = lex.audit.verify()
    refused = sum(1 for r in rows if not r["allowed"])
    lex.audit.append(actor, "lex_drill", "boundary", "passed" if refused == len(rows) else "FAILED",
                     {"refused": refused, "attempts": len(rows), "chain_ok": verify["ok"]})
    return {"attempts": rows, "refused": refused, "total": len(rows), "passed": refused == len(rows),
            "audit": lex.audit.verify()}
