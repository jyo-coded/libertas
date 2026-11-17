"""ShadowNet demo control panel. Bound to 127.0.0.1 only and never published on Tor."""
from __future__ import annotations

import html
import json
from urllib.parse import quote

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from libertas.common.timeutil import now_iso
from libertas.config import PATHS

from .sites import CSS, human
from .store import FORUM_SECTIONS, Store
from .world import PRESETS

esc = html.escape


def panel_app(store: Store) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def back(msg: str) -> RedirectResponse:
        return RedirectResponse(url="/?msg=" + quote(msg), status_code=303)

    @app.get("/")
    def index(msg: str = ""):
        reg = json.loads(PATHS.shadownet_registry.read_text()) if PATHS.shadownet_registry.exists() else {}
        sites = "".join(
            f'<tr><td>{esc(s["name"])}</td><td><code>http://{esc(s["onion"])}.onion</code></td>'
            f'<td>{"private (client auth)" if s["private"] else "public"}</td><td>{"armed" if s.get("pow") else "—"}</td></tr>'
            for s in reg.get("sites", []))
        key = reg.get("client_auth", {}).get("private_key_b32", "")
        presets = "".join(f'<form method="post" action="/preset/{k}" style="display:inline-block;margin:4px">'
                          f'<button>{esc(label)}</button></form>' for k, (label, _) in PRESETS.items())
        members = "".join(f'<option>{esc(m["name"])}</option>' for m in store.members())
        sections = "".join(f'<option value="{fid}">{esc(n)}</option>' for fid, n in FORUM_SECTIONS.items())

        def rows(items, kind, key_field, label_field):
            return "".join(f'<tr><td>{esc(str(i[label_field]))}</td><td>{human(i["created_at"])}</td><td>'
                           f'<form method="post" action="/{kind}/delete/{esc(str(i[key_field]))}"><button>delete</button>'
                           '</form></td></tr>' for i in items)

        hits = "".join(f'<tr><td>{esc(h["at"])}</td><td>{esc(h["path"])}</td><td>{esc(h["ua"])}</td></tr>'
                       for h in store.honeypot_hits()) or '<tr><td colspan="3">none — good</td></tr>'
        body = f"""
<h2>ShadowNet control panel <small>(local only, not on Tor)</small></h2>
{f'<p class="meta" style="color:#8be28b">✔ {esc(msg)}</p>' if msg else ''}
<table class="grid"><tr><th>Site</th><th>Onion</th><th>Access</th><th>PoW</th></tr>{sites}</table>
<p class="meta">To open private sites in Tor Browser, paste this client key when it asks:
<code>{esc(key)}</code></p>
<h3>Live demo presets</h3>{presets}
<h3>Custom forum post</h3>
<form method="post" action="/forum/post"><select name="alias">{members}</select>
<select name="fid">{sections}</select><br><input name="title" size="80" placeholder="title"><br>
<textarea name="body" rows="6" cols="90" placeholder="post body"></textarea><br><button>Post</button></form>
<h3>Forum threads</h3><table class="grid">{rows(store.threads(limit=12), "forum", "tid", "title")}</table>
<h3>Market listings</h3><table class="grid">{rows(store.listings(limit=8), "market", "id", "title")}</table>
<h3>Leak blog victims</h3><table class="grid">{rows(store.victims(), "leak", "id", "name")}</table>
<h3>Pastes</h3><table class="grid">{rows(store.pastes(limit=8), "paste", "id", "title")}</table>
<h3>Honeypot hits (crawler must never appear here)</h3>
<table class="grid"><tr><th>When</th><th>Path</th><th>User agent</th></tr>{hits}</table>"""
        return HTMLResponse(f'<!doctype html><html><head><meta charset="utf-8"><title>ShadowNet panel</title>'
                            f'<style>{CSS}</style></head><body><main>{body}</main></body></html>')

    @app.post("/preset/{key}")
    def preset(key: str):
        if key not in PRESETS:
            return back("unknown preset")
        return back(PRESETS[key][1](store))

    @app.post("/forum/post")
    def forum_post(alias: str = Form(...), fid: int = Form(...), title: str = Form(...), body: str = Form(...)):
        m = store.member_by_name(alias)
        if not m or not title.strip():
            return back("alias and title are required")
        tid = store.create_thread(fid, title.strip(), m["uid"], body, now_iso()[:19] + "+00:00")
        return back(f"posted thread {tid} as {alias}")

    @app.post("/forum/delete/{tid}")
    def forum_delete(tid: int):
        store.delete_thread(tid)
        return back(f"deleted thread {tid}")

    @app.post("/market/delete/{lid}")
    def market_delete(lid: int):
        store.delete_listing(lid)
        return back(f"deleted listing {lid}")

    @app.post("/leak/delete/{vid}")
    def leak_delete(vid: int):
        store.delete_victim(vid)
        return back(f"removed victim {vid}")

    @app.post("/paste/delete/{pid}")
    def paste_delete(pid: str):
        store.delete_paste(pid)
        return back(f"deleted paste {pid}")

    return app
