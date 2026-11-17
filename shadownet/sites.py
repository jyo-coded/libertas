"""The four ShadowNet sites, served on localhost and published as onion services by ShadowNet's own tor.

All output is escaped. Pages carry a SIMULATION banner. The forum footer hides a honeypot link, as real
forums do, so we can prove the Libertas crawler never follows links a human couldn't see.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from email.utils import format_datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from libertas.common.timeutil import now_iso

from .store import FORUM_SECTIONS, Store

esc = html.escape
BANNER = ('<div class="sim">⚠ SIMULATION — ShadowNet is a training environment for Libertas. '
          'All names, data and events are fictional.</div>')
CSS = """
body{margin:0;background:#14161a;color:#d6d9de;font:14px/1.5 Verdana,Arial,sans-serif}
.sim{background:#5c1a1a;color:#ffd7d7;padding:6px 12px;font-size:12px;text-align:center}
header{background:#1f2329;padding:12px 18px;display:flex;gap:18px;align-items:center;border-bottom:1px solid #2c323a}
header .brand{color:#e8b04a;font-weight:bold;font-size:18px;text-decoration:none}
nav a,main a{color:#8fb8e8}
main{max-width:980px;margin:18px auto;padding:0 14px}
table.grid{width:100%;border-collapse:collapse;margin-bottom:18px}
.grid th,.grid td{border:1px solid #2c323a;padding:6px 8px;text-align:left}
.grid th{background:#232831}
.post{border:1px solid #2c323a;margin-bottom:12px;background:#1a1d22}
.post_author{background:#232831;padding:6px 10px;font-weight:bold}
.usertitle{font-weight:normal;color:#9aa3ad;margin-left:8px;font-size:12px}
.post_head{padding:4px 10px;font-size:12px;color:#9aa3ad;border-bottom:1px solid #2c323a}
.post_body{padding:10px;white-space:normal;font-family:Consolas,monospace;font-size:13px}
.signature{padding:4px 10px;color:#7d8590;font-size:12px;border-top:1px dashed #2c323a}
.listing,.victim{border:1px solid #2c323a;padding:10px;margin-bottom:10px;background:#1a1d22}
.meta{color:#9aa3ad;font-size:12px}
.status-countdown{color:#ff8a65;font-weight:bold}.status-published{color:#e57373;font-weight:bold}
pre{background:#0f1114;padding:10px;overflow-x:auto;border:1px solid #2c323a}
.error{padding:30px;text-align:center;color:#ff8a65}
footer{text-align:center;color:#5d646d;font-size:11px;padding:20px}
"""


def page(site: str, title: str, body: str, nav: str = "", trap: bool = False) -> str:
    trap_html = '<a href="/admin/trap" style="display:none">admin panel</a>' if trap else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(title)} — {esc(site)}</title>'
            f'<style>{CSS}</style></head><body>{BANNER}<header><a class="brand" href="/">{esc(site)}</a>'
            f'<nav>{nav}</nav></header><main>{body}</main><footer>{esc(site)} · simulated {trap_html}</footer>'
            '</body></html>')


def human(ts: str) -> str:
    return datetime.fromisoformat(ts).strftime("%d-%m-%Y, %I:%M %p UTC")


def text_html(text: str) -> str:
    return esc(text).replace("\n", "<br>")


def _html(content: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(content, status_code=status)


def _bare_app() -> FastAPI:
    return FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# ---------------- Kaal Forum (MyBB-style) ----------------
def forum_app(store: Store) -> FastAPI:
    app, site = _bare_app(), "Kaal Forum"
    nav = '<a href="/">Index</a> · <a href="/syndication.php">RSS</a>'

    def thread_rows(threads) -> str:
        return "".join(
            f'<tr><td><a href="/showthread.php?tid={t["tid"]}">{esc(t["title"])}</a></td>'
            f'<td><a href="/member.php?uid={t["author_uid"]}">{esc(t["author"])}</a></td><td>{t["posts"]}</td>'
            f'<td><time datetime="{t["created_at"]}">{human(t["created_at"])}</time></td></tr>' for t in threads)

    @app.get("/")
    def index():
        counts = store.section_counts()
        sections = "".join(f'<tr><td><a href="/forumdisplay.php?fid={fid}">{esc(name)}</a></td>'
                           f'<td>{counts.get(fid, 0)}</td></tr>' for fid, name in FORUM_SECTIONS.items())
        body = (f'<h2>Forums</h2><table class="grid"><tr><th>Section</th><th>Threads</th></tr>{sections}</table>'
                '<h2>Latest threads</h2><table class="grid"><tr><th>Thread</th><th>Author</th><th>Posts</th>'
                f'<th>Posted</th></tr>{thread_rows(store.threads(limit=15))}</table>')
        return _html(page(site, "Index", body, nav, trap=True))

    @app.get("/forumdisplay.php")
    def forumdisplay(fid: int = 1):
        name = FORUM_SECTIONS.get(fid)
        if not name:
            return _html(page(site, "Error", '<div class="error">Invalid forum specified.</div>', nav), 404)
        body = (f'<h2>{esc(name)}</h2><table class="grid"><tr><th>Thread</th><th>Author</th><th>Posts</th>'
                f'<th>Posted</th></tr>{thread_rows(store.threads(fid=fid, limit=100))}</table>')
        return _html(page(site, name, body, nav, trap=True))

    @app.get("/showthread.php")
    def showthread(tid: int = 0):
        t = store.thread(tid)
        if not t:
            return _html(page(site, "Error", '<div class="error">The specified thread does not exist.</div>', nav), 404)
        posts = ""
        for p in store.thread_posts(tid):
            sig = f'<div class="signature">{esc(p["signature"])}</div>' if p["signature"] else ""
            posts += (f'<div class="post" id="post_{p["pid"]}"><div class="post_author">'
                      f'<a href="/member.php?uid={p["uid"]}">{esc(p["author"])}</a>'
                      f'<span class="usertitle">{esc(p["mtitle"] or "")}</span></div>'
                      f'<div class="post_head"><span class="post_date" data-ts="{p["created_at"]}">'
                      f'{human(p["created_at"])}</span></div><div class="post_body">{text_html(p["body"])}</div>{sig}</div>')
        body = (f'<div class="breadcrumb"><a href="/forumdisplay.php?fid={t["fid"]}">{esc(FORUM_SECTIONS.get(t["fid"], ""))}'
                f'</a></div><h2 class="thread_title">{esc(t["title"])}</h2>{posts}')
        return _html(page(site, t["title"], body, nav, trap=True))

    @app.get("/member.php")
    def member(uid: int = 0):
        m = store.member(uid)
        if not m:
            return _html(page(site, "Error", '<div class="error">The member you specified is invalid.</div>', nav), 404)
        pgp = f'<tr><th>PGP fingerprint</th><td><code>{esc(m["pgp"])}</code></td></tr>' if m["pgp"] else ""
        contact = f'<tr><th>Contact</th><td>{esc(m["contact"])}</td></tr>' if m["contact"] else ""
        body = (f'<h2 class="profile_name">{esc(m["name"])}</h2><table class="grid">'
                f'<tr><th>Title</th><td>{esc(m["title"] or "")}</td></tr>'
                f'<tr><th>Joined</th><td><time datetime="{m["joined"]}">{human(m["joined"])}</time></td></tr>'
                f'<tr><th>Posts</th><td>{store.post_count(uid)}</td></tr>{pgp}{contact}'
                f'<tr><th>Signature</th><td>{esc(m["signature"] or "")}</td></tr></table>')
        return _html(page(site, m["name"], body, nav, trap=True))

    @app.get("/syndication.php")
    def rss(request: Request):
        base = f"http://{request.headers.get('host', 'localhost')}"
        items = ""
        for t in store.threads(limit=20):
            posts = store.thread_posts(t["tid"])
            first = posts[0]["body"] if posts else ""
            items += (f"<item><title>{esc(t['title'])}</title><link>{base}/showthread.php?tid={t['tid']}</link>"
                      f"<guid isPermaLink=\"false\">thread-{t['tid']}</guid>"
                      f"<pubDate>{format_datetime(datetime.fromisoformat(t['created_at']))}</pubDate>"
                      f"<dc:creator>{esc(t['author'])}</dc:creator>"
                      f"<category>{esc(FORUM_SECTIONS.get(t['fid'], ''))}</category>"
                      f"<description>{esc(first[:200])}</description></item>")
        xml = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">'
               f'<channel><title>Kaal Forum - Latest Threads</title><link>{base}/</link>'
               f'<description>SIMULATION</description>{items}</channel></rss>')
        return Response(xml, media_type="application/rss+xml")

    @app.get("/admin/trap")
    def trap(request: Request):
        store.honeypot_hit(now_iso(), "/admin/trap", request.headers.get("user-agent", ""))
        return _html(page(site, "Denied", '<div class="error">Access denied. This visit was logged.</div>', nav), 403)

    return app


# ---------------- Sona Bazaar (marketplace) ----------------
def market_app(store: Store) -> FastAPI:
    app, site = _bare_app(), "Sona Bazaar"
    nav = '<a href="/">Listings</a> · <a href="/mirrors.txt">Mirrors</a>'

    def card(l) -> str:
        return (f'<div class="listing" data-id="{l["id"]}"><a class="ltitle" href="/listing/{l["id"]}">{esc(l["title"])}</a>'
                f'<div class="meta">by <a class="vendor" href="/vendor/{esc(l["vendor"])}">{esc(l["vendor"])}</a> · '
                f'{esc(l["category"])} · ${l["price_usd"]:,.0f} · <time datetime="{l["created_at"]}">'
                f'{human(l["created_at"])}</time></div></div>')

    @app.get("/")
    def index():
        return _html(page(site, "Listings", "<h2>Newest listings</h2>" + "".join(card(l) for l in store.listings()), nav))

    @app.get("/listing/{lid}")
    def listing(lid: int):
        l = store.listing(lid)
        if not l:
            return _html(page(site, "Not found", '<div class="error">Listing not found or removed by vendor.</div>', nav), 404)
        v = store.vendor(l["vendor"])
        body = (f'<h2 class="ltitle">{esc(l["title"])}</h2><div class="meta">Vendor: <a class="vendor" '
                f'href="/vendor/{esc(l["vendor"])}">{esc(l["vendor"])}</a> · Category: {esc(l["category"])} · '
                f'Listed <time datetime="{l["created_at"]}">{human(l["created_at"])}</time></div>'
                f'<table class="grid"><tr><th>Price</th><td>${l["price_usd"]:,.0f} (escrow)</td></tr>'
                f'<tr><th>Vendor PGP</th><td><code>{esc(v["pgp"] if v else "")}</code></td></tr>'
                f'<tr><th>Direct deal BTC</th><td><code>{esc(v["wallet"] if v else "")}</code></td></tr></table>'
                f'<div class="description">{text_html(l["body"])}</div>')
        return _html(page(site, l["title"], body, nav))

    @app.get("/vendor/{name}")
    def vendor(name: str):
        v = store.vendor(name)
        if not v:
            return _html(page(site, "Not found", '<div class="error">Vendor not found.</div>', nav), 404)
        body = (f'<h2>{esc(v["name"])}</h2><table class="grid"><tr><th>Rating</th><td>{v["rating"]} / 5</td></tr>'
                f'<tr><th>Sales</th><td>{v["sales"]}</td></tr><tr><th>Joined</th><td>{human(v["joined"])}</td></tr>'
                f'<tr><th>PGP</th><td><code>{esc(v["pgp"])}</code></td></tr><tr><th>About</th><td>{esc(v["about"])}</td></tr>'
                '</table><h3>Listings</h3>' + "".join(card(l) for l in store.listings(vendor=name)))
        return _html(page(site, v["name"], body, nav))

    @app.get("/mirrors.txt")
    def mirrors(request: Request):
        host = request.headers.get("host", "localhost")
        return PlainTextResponse("-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\nSona Bazaar official mirrors:\n"
                                 f"http://{host}/\n\n(simulated signature, ShadowNet)\n-----END PGP SIGNATURE-----\n")

    return app


# ---------------- ShadowLock (ransomware leak blog) ----------------
def leakblog_app(store: Store) -> FastAPI:
    app, site = _bare_app(), "ShadowLock"
    nav = '<a href="/">Victims</a> · <a href="/api/victims.json">API</a>'

    @app.get("/")
    def index():
        cards = "".join(
            f'<div class="victim" data-id="{v["id"]}"><a href="/victim/{v["id"]}"><b>{esc(v["name"])}</b></a> '
            f'<span class="meta">{esc(v["country"])} · {esc(v["sector"])} · {esc(v["data_size"])}</span><br>'
            f'<span class="status-{esc(v["status"])}">{esc(v["status"].upper())}</span> · deadline '
            f'<time class="countdown" datetime="{v["deadline"]}">{human(v["deadline"])}</time></div>'
            for v in store.victims())
        return _html(page(site, "Victims", "<h2>Companies that refused to cooperate</h2>" + cards, nav))

    @app.get("/victim/{vid}")
    def victim(vid: int):
        v = store.victim(vid)
        if not v:
            return _html(page(site, "Not found", '<div class="error">Not found.</div>', nav), 404)
        body = (f'<h2 class="vname">{esc(v["name"])}</h2><div class="meta">{esc(v["country"])} · {esc(v["sector"])} · '
                f'website {esc(v["website"])} · {esc(v["data_size"])}</div><p class="status-{esc(v["status"])}">'
                f'{esc(v["status"].upper())} — deadline <time class="countdown" datetime="{v["deadline"]}">'
                f'{human(v["deadline"])}</time></p><div class="description">{text_html(v["description"])}</div>')
        return _html(page(site, v["name"], body, nav))

    @app.get("/api/victims.json")
    def api(request: Request):
        host = request.headers.get("host", "localhost")
        data = {"group": "ShadowLock", "simulation": True, "victims": [
            {"id": v["id"], "name": v["name"], "country": v["country"], "sector": v["sector"], "website": v["website"],
             "deadline": v["deadline"], "status": v["status"], "data_size": v["data_size"], "posted_at": v["created_at"],
             "url": f"http://{host}/victim/{v['id']}"} for v in store.victims()]}
        return Response(json.dumps(data), media_type="application/json")

    return app


# ---------------- DeadDrop (paste site) ----------------
def paste_app(store: Store) -> FastAPI:
    app, site = _bare_app(), "DeadDrop"
    nav = '<a href="/">Recent pastes</a>'

    @app.get("/")
    def index():
        rows = "".join(f'<tr class="paste" data-id="{p["id"]}"><td><a href="/p/{p["id"]}">{esc(p["title"])}</a></td>'
                       f'<td class="author">{esc(p["author"])}</td><td><time datetime="{p["created_at"]}">'
                       f'{human(p["created_at"])}</time></td></tr>' for p in store.pastes())
        return _html(page(site, "Recent", f'<h2>Recent pastes</h2><table class="grid"><tr><th>Title</th><th>Author</th>'
                                          f'<th>Posted</th></tr>{rows}</table>', nav))

    @app.get("/p/{pid}")
    def view(pid: str):
        p = store.paste(pid)
        if not p:
            return _html(page(site, "Not found", '<div class="error">Paste not found or expired.</div>', nav), 404)
        return _html(page(site, p["title"], f'<h2>{esc(p["title"])}</h2><div class="meta">by {esc(p["author"])} · '
                                            f'{human(p["created_at"])} · <a href="/raw/{p["id"]}">raw</a></div>'
                                            f'<pre>{esc(p["body"])}</pre>', nav))

    @app.get("/raw/{pid}")
    def raw(pid: str):
        p = store.paste(pid)
        if not p:
            return PlainTextResponse("Paste not found or expired.", status_code=404)
        return PlainTextResponse(p["body"])

    return app


SITE_APPS = {"forum": forum_app, "market": market_app, "leakblog": leakblog_app, "paste": paste_app}
