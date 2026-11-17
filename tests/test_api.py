"""API smoke test: routes load, security headers are set, the kill switch works through the API, and the localhost
hardening refuses cross-site writes, foreign hosts (DNS rebinding) and foreign WebSocket origins."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from libertas import db
from libertas.api.app import create_app
from libertas.config import Settings
from libertas.lex.audit import AuditLog
from libertas.lex.policy import Lex
from libertas.vigiles.alerts import Vigiles
from libertas.vigiles.bus import Bus


def test_api_routes_and_kill_switch(tmp_path):
    conn = db.connect(tmp_path / "a.db")
    audit = AuditLog(conn)
    lex = Lex(audit, mode="development", kill_file=tmp_path / "KILL")
    bus = Bus()
    ctx = SimpleNamespace(conn=conn, audit=audit, lex=lex, bus=bus, vigiles=Vigiles(conn, audit, bus, Settings()),
                          aquila=SimpleNamespace(health={}, queue=asyncio.Queue()), settings=Settings())
    c = TestClient(create_app(ctx, allowed_hosts=("testserver",)), headers={"X-Libertas-Client": "forum"})
    page = c.get("/")
    assert page.status_code == 200 and "script-src 'self'" in page.headers["content-security-policy"]
    assert c.get("/static/app.js").status_code == 200
    assert c.get("/static/../config.py").status_code == 404
    status = c.get("/api/status").json()
    assert status["kill_engaged"] is False and status["audit"]["ok"]
    assert c.get("/api/alerts").json() == []
    assert c.post("/api/kill", json={"reason": "drill"}).json()["kill_engaged"] is True
    assert (tmp_path / "KILL").exists() and c.get("/api/status").json()["kill_engaged"] is True
    assert c.post("/api/resume").json()["kill_engaged"] is False
    assert c.get("/api/audit/verify").json()["ok"]


def test_localhost_hardening(tmp_path):
    conn = db.connect(tmp_path / "a.db")
    audit = AuditLog(conn)
    lex = Lex(audit, mode="development", kill_file=tmp_path / "KILL")
    bus = Bus()
    ctx = SimpleNamespace(conn=conn, audit=audit, lex=lex, bus=bus, vigiles=Vigiles(conn, audit, bus, Settings()),
                          aquila=SimpleNamespace(health={}, queue=asyncio.Queue()), settings=Settings())
    app = create_app(ctx, allowed_hosts=("testserver",))
    bare = TestClient(app)
    # a cross-site form or no-cors fetch cannot attach the client header, so the write is refused
    assert bare.post("/api/resume").status_code == 403
    assert bare.post("/api/kill", json={"reason": "csrf"}).status_code == 403 and not (tmp_path / "KILL").exists()
    # the header alone is not enough when the browser says the request came from another site
    hdr = {"X-Libertas-Client": "forum"}
    assert bare.post("/api/kill", json={"reason": "x"}, headers={**hdr, "Origin": "http://evil.example"}).status_code == 403
    assert bare.post("/api/kill", json={"reason": "drill"}, headers=hdr).status_code == 200
    # DNS rebinding: a foreign Host header never reaches a route
    assert TestClient(app, base_url="http://attacker.example").get("/api/status").status_code == 400
    # cross-site WebSocket hijacking: a foreign Origin is closed before the stream opens
    with pytest.raises(WebSocketDisconnect):
        with bare.websocket_connect("/ws", headers={"Origin": "http://evil.example"}) as ws:
            ws.receive_text()
