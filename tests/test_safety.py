"""Gate A: the safety invariants of blueprint §11.14 and §17. These must stay green."""
import asyncio
import gzip

import httpx
import pytest
from defusedxml import DTDForbidden, EntitiesForbidden

from libertas.common.onion import find_onions, is_valid_v3, random_v3_label
from libertas.config import Settings
from libertas.db import connect
from libertas.janus.quarantine import Quarantine
from libertas.janus.sanitize import parse_html, parse_xml
from libertas.lex.audit import AuditLog
from libertas.lex.policy import Lex
from libertas.speculatores.fetcher import Refused, WatchSession, decompress_capped


@pytest.fixture
def env(tmp_path):
    conn = connect(tmp_path / "t.db")
    audit = AuditLog(conn)
    allowed = random_v3_label()
    lex = Lex(audit, mode="development", kill_file=tmp_path / "KILL", allowlist={allowed})
    return conn, audit, lex, allowed


# ---------- onion addresses ----------
def test_onion_checksum_and_extraction():
    label = random_v3_label()
    assert is_valid_v3(label) and is_valid_v3(f"www.{label}.onion")
    broken = label[:10] + ("a" if label[10] != "a" else "b") + label[11:]
    assert not is_valid_v3(broken)
    assert find_onions(f"mirror: http://{label}.onion/x and fake {broken}.onion") == [label]


# ---------- Lex ----------
def test_lex_allows_only_allowlisted_onion_get(env):
    _, _, lex, allowed = env
    assert lex.check_fetch("GET", f"http://{allowed}.onion/showthread.php?tid=1").allowed


@pytest.mark.parametrize("url,needle", [
    ("https://example.com/", "clearnet"),
    ("http://127.0.0.1:8601/", "clearnet"),
    ("ftp://x.onion/", "scheme"),
])
def test_lex_refuses_non_onion(env, url, needle):
    _, _, lex, _ = env
    d = lex.check_fetch("GET", url)
    assert not d.allowed and needle in d.reason


def test_lex_refuses_unlisted_and_invalid_onions(env):
    _, _, lex, allowed = env
    assert "allowlist" in lex.check_fetch("GET", f"http://{random_v3_label()}.onion/").reason
    broken = allowed[:10] + ("a" if allowed[10] != "a" else "b") + allowed[11:]
    assert "checksum" in lex.check_fetch("GET", f"http://{broken}.onion/").reason


def test_lex_refuses_non_get_and_odd_ports(env):
    _, _, lex, allowed = env
    assert "only GET" in lex.check_fetch("POST", f"http://{allowed}.onion/login").reason
    assert "port" in lex.check_fetch("GET", f"http://{allowed}.onion:9050/").reason
    assert "credentials" in lex.check_fetch("GET", f"http://u:p@{allowed}.onion/").reason


@pytest.mark.parametrize("ext", [".zip", ".rar", ".exe", ".pdf", ".png", ".sql", ".csv", ".js", ".apk"])
def test_lex_refuses_file_downloads(env, ext):
    _, _, lex, allowed = env
    d = lex.check_fetch("GET", f"http://{allowed}.onion/files/sample{ext}")
    assert not d.allowed and "file download refused" in d.reason


def test_kill_switch_blocks_everything(env):
    _, _, lex, allowed = env
    lex.engage_kill("test", "drill")
    assert "kill switch" in lex.check_fetch("GET", f"http://{allowed}.onion/").reason
    lex.release_kill("test")
    assert lex.check_fetch("GET", f"http://{allowed}.onion/").allowed


def test_audit_chain_detects_tampering(env):
    conn, audit, lex, _ = env
    lex.check_fetch("GET", "https://example.com/")
    lex.check_fetch("POST", "https://example.org/")
    assert audit.verify()["ok"] and audit.verify()["entries_checked"] == 2
    conn.execute("UPDATE audit_log SET decision='allow' WHERE seq=1")
    assert not audit.verify()["ok"]


# ---------- Janus: sanitizer, XML, quarantine ----------
HOSTILE_HTML = b"""<html><head><title>Kaal Forum</title><script>alert('pwn')</script>
<style>body{background:url(http://tracker.example/x.png)}</style></head>
<body onload="steal()"><h1>Fresh DB</h1><iframe src="http://evil.example/"></iframe>
<img src="http://beacon.example/p.gif" onerror="steal()">
<a href="javascript:steal()">click</a><a href="/files/sample.zip">sample</a>
<a href="/showthread.php?tid=2">next</a><a href="/trap" style="display:none">trap</a>
<svg><script>alert(2)</script></svg><p>Price 2 BTC</p></body></html>"""


def test_sanitizer_strips_active_content():
    doc = parse_html(HOSTILE_HTML, "http://x.onion/", keep_soup=True)
    assert "alert" not in doc.text and "steal" not in doc.text
    assert "Fresh DB" in doc.text and "Price 2 BTC" in doc.text
    assert not any(l.url.startswith("javascript:") for l in doc.links)
    by_text = {l.text: l for l in doc.links}
    assert by_text["sample"].is_file and by_text["sample"].ext == ".zip"
    assert by_text["trap"].hidden and not by_text["next"].hidden
    assert doc.removed_elements >= 4
    html_after = str(doc.soup)
    assert "onload" not in html_after and "onerror" not in html_after and "<script" not in html_after


def test_xml_entity_attacks_blocked():
    bomb = b"""<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;">]>
    <rss><channel><title>&lol2;</title></channel></rss>"""
    with pytest.raises((EntitiesForbidden, DTDForbidden)):
        parse_xml(bomb)


def test_quarantine_has_no_extension_and_verifies(tmp_path):
    q = Quarantine(tmp_path / "q")
    data = b"<html><script>x</script></html>"
    sha = q.put(data)
    path = q.path_for(sha)
    assert path.suffix == "" and path.read_bytes()[:2] == b"\x1f\x8b"
    assert q.get(sha) == data


def test_decompression_bomb_refused():
    bomb = gzip.compress(b"\0" * 50_000_000)
    assert len(bomb) < 100_000
    with pytest.raises(Refused):
        decompress_capped(bomb, "gzip", 2_000_000)
    assert decompress_capped(gzip.compress(b"hello"), "gzip", 100) == b"hello"
    with pytest.raises(Refused):
        decompress_capped(b"x", "br", 100)


# ---------- fetcher behaviour (mock transport, no network) ----------
def _session(lex, handler):
    return WatchSession("test", Settings(), lex, transport=httpx.MockTransport(handler))


def test_fetcher_refuses_binary_types(env):
    _, _, lex, allowed = env
    s = _session(lex, lambda r: httpx.Response(200, headers={"content-type": "application/octet-stream"}, content=b"MZ\x90"))
    res = asyncio.run(s.get(f"http://{allowed}.onion/download"))
    assert res.refused and "content-type" in res.refused and res.body is None


def test_fetcher_blocks_redirect_to_clearnet(env):
    _, _, lex, allowed = env
    s = _session(lex, lambda r: httpx.Response(302, headers={"location": "https://tracker.example/x"}))
    res = asyncio.run(s.get(f"http://{allowed}.onion/"))
    assert "clearnet" in res.refused


def test_fetcher_refuses_oversize(env):
    _, _, lex, allowed = env
    big = b"a" * 2_500_000
    s = _session(lex, lambda r: httpx.Response(200, headers={"content-type": "text/plain"}, content=big))
    assert "cap" in asyncio.run(s.get(f"http://{allowed}.onion/big")).refused


def test_fetcher_returns_text(env):
    _, _, lex, allowed = env
    s = _session(lex, lambda r: httpx.Response(200, headers={"content-type": "text/html; charset=utf-8",
                                                             "etag": '"v1"'}, stream=httpx.ByteStream(HOSTILE_HTML)))
    res = asyncio.run(s.get(f"http://{allowed}.onion/"))
    assert res.ok and res.body == HOSTILE_HTML and res.status == 200


def test_fetcher_streams_gzip_under_cap(env):
    _, _, lex, allowed = env
    bomb = gzip.compress(b"A" * 20_000_000)
    s = _session(lex, lambda r: httpx.Response(200, headers={"content-type": "text/html", "content-encoding": "gzip"},
                                               stream=httpx.ByteStream(bomb)))
    res = asyncio.run(s.get(f"http://{allowed}.onion/"))
    assert res.refused and "bomb" in res.refused
