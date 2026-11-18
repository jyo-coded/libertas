"""Libertas API (localhost only). Captured content is only ever returned as data, never rendered as HTML.
The minimal live page uses textContent exclusively, and the M6 React dashboard keeps the same rule."""
from __future__ import annotations

import asyncio
import json
import statistics
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..codex.pack import PACK_ID_RE
from ..common.timeutil import now_iso
from ..config import PATHS
from ..interpres.india import mask_pii
from ..lex.drill import run as lex_drill

STATIC = Path(__file__).parent / "static"
# Explicit types: Windows registry MIME maps can turn .js into text/plain, which browsers refuse for modules.
ASSET_TYPES = {".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".woff": "font/woff",
               ".svg": "image/svg+xml", ".png": "image/png"}
FORUM = Path(__file__).parent / "forum"  # the built React console (web/ → npm run build)
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self' ws://127.0.0.1:8700 ws://localhost:8700; frame-ancestors 'none'; base-uri 'none'; "
       "form-action 'self'")


class KillRequest(BaseModel):
    reason: str = "operator request"


CLIENT_HEADER = "x-libertas-client"
DEV_PORT = 5173  # the Vite dev server proxies /api and /ws while the Forum is being built


def create_app(ctx, allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")) -> FastAPI:
    """Localhost hardening, because any web page the officer opens can aim requests at 127.0.0.1:
    - the Host header must be local (defeats DNS rebinding);
    - every write must carry X-Libertas-Client, which a cross-site page cannot attach without a CORS preflight
      that this API never grants (defeats CSRF on kill/resume/ack/evidence);
    - the live socket refuses foreign Origins (defeats cross-site WebSocket hijacking of the alert stream)."""
    app = FastAPI(title="Libertas API", docs_url="/api/docs", redoc_url=None)
    conn = ctx.conn
    port = getattr(ctx.settings, "api_port", 8700)
    origins = {f"http://{h}:{p}" for h in allowed_hosts for p in (port, DEV_PORT)}

    def origin_ok(origin: str | None) -> bool:
        return origin is None or origin in origins

    @app.middleware("http")
    async def security_headers(request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get(CLIENT_HEADER) != "forum" or not origin_ok(request.headers.get("origin")):
                return JSONResponse({"detail": "refused: writes must come from the Forum console"}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))

    @app.get("/")
    async def index():
        forum = FORUM / "index.html"
        # no-cache: the page names hashed bundles, so it must be revalidated or a rebuild never reaches the officer
        return FileResponse(forum if forum.exists() else STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/classic")
    async def classic():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/assets/{name}")
    async def forum_asset(name: str):
        path = (FORUM / "assets" / name).resolve()
        if path.parent != (FORUM / "assets").resolve() or not path.is_file() or path.suffix not in ASSET_TYPES:
            raise HTTPException(404)
        return FileResponse(path, media_type=ASSET_TYPES[path.suffix],
                            headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/favicon.svg")
    async def favicon():
        path = FORUM / "favicon.svg"
        if not path.exists():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/svg+xml")

    @app.get("/static/{name}")
    async def static(name: str):
        path = STATIC / name
        if path.parent != STATIC or not path.exists():
            raise HTTPException(404)
        return FileResponse(path)

    @app.get("/api/status")
    async def status():
        lags = [r[0] for r in conn.execute(
            "SELECT detection_lag_s FROM items WHERE detection_lag_s IS NOT NULL AND detection_lag_s BETWEEN 0 AND 86400")]
        ttd = None
        if lags:
            lags.sort()
            ttd = {"n": len(lags), "median_s": round(statistics.median(lags), 1),
                   "p95_s": round(lags[min(len(lags) - 1, int(0.95 * len(lags)))], 1), "max_s": round(lags[-1], 1)}
        sev = {r[0]: r[1] for r in conn.execute("SELECT severity, COUNT(*) FROM alerts GROUP BY severity")}
        sources = []
        for s in conn.execute("SELECT * FROM sources ORDER BY id"):
            d = {k: s[k] for k in s.keys()}
            d["health"] = ctx.aquila.health.get(s["id"], {})
            d["items"] = conn.execute("SELECT COUNT(*) FROM items WHERE source_id=?", (s["id"],)).fetchone()[0]
            sources.append(d)
        return {"mode": ctx.settings.mode, "unit": ctx.settings.unit_name, "kill_engaged": ctx.lex.kill_engaged(),
                "simulation": True,
                "lex": {"mode": ctx.lex.mode, "allowlist_size": len(ctx.lex.allowlist),
                        "blocklist_size": len(ctx.lex.blocklist_md5)},
                "sources": sources, "ttd": ttd, "alerts_by_severity": sev,
                "counts": {k: conn.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0]
                           for k in ("items", "captures", "alerts", "indicators", "audit_log")}
                | {"responses_received": conn.execute("SELECT COUNT(*) FROM captures WHERE outcome LIKE 'http_%'").fetchone()[0]},
                "queue": ctx.aquila.queue.qsize(), "audit": ctx.audit.verify(),
                "heartbeat": ctx.aquila.heartbeat.summary() if hasattr(ctx.aquila, "heartbeat") else None,
                "tor": {k: v for k, v in (getattr(ctx, "tor", None) or {}).items() if k != "proc"} or None}

    @app.get("/api/alerts")
    async def alerts(limit: int = 50, include_historical: bool = True):
        sql = "SELECT id FROM alerts" + ("" if include_historical else " WHERE status != 'historical'")
        sql += " ORDER BY CASE status WHEN 'historical' THEN 1 ELSE 0 END, created_at DESC LIMIT ?"
        return [ctx.vigiles.payload(r[0]) for r in conn.execute(sql, (min(limit, 500),))]

    @app.post("/api/alerts/{alert_id}/ack")
    async def acknowledge(alert_id: int):
        row = conn.execute("SELECT id, status, item_id, severity FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        if row["status"] != "acknowledged":
            conn.execute("UPDATE alerts SET status='acknowledged', updated_at=? WHERE id=?", (now_iso(), alert_id))
            ctx.audit.append("dashboard-operator", "alert_acknowledged", f"item:{row['item_id']}", row["severity"],
                             {"alert": alert_id, "previous_status": row["status"]})
            payload = ctx.vigiles.payload(alert_id)
            ctx.bus.publish({"type": "alert_updated", "alert": payload})
        return ctx.vigiles.payload(alert_id)

    @app.get("/api/items")
    async def items(q: str = "", source: str = "", limit: int = 50):
        sql, args = "SELECT id, source_id, kind, title, author, posted_at, first_seen, deleted_at FROM items WHERE 1=1", []
        if q:
            sql += " AND (title LIKE ? OR body_text LIKE ?)"
            args += [f"%{q}%", f"%{q}%"]
        if source:
            sql += " AND source_id=?"
            args.append(source)
        sql += " ORDER BY first_seen DESC LIMIT ?"
        args.append(min(limit, 500))
        return [{**dict(r), "title": mask_pii(r["title"] or "")} for r in conn.execute(sql, args)]

    @app.get("/api/items/{item_id}")
    async def item(item_id: int):
        r = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not r:
            raise HTTPException(404)
        d = dict(r)
        d["body_text"] = mask_pii(d["body_text"] or "")  # the sealed capture keeps the exact bytes
        d["title"] = mask_pii(d["title"] or "")
        d["extra"] = json.loads(d.pop("extra_json") or "{}")
        d["indicators"] = [dict(x) for x in conn.execute(
            "SELECT kind, value, display, valid, sensitive FROM indicators WHERE item_id=?", (item_id,))]
        for ind in d["indicators"]:
            if ind["sensitive"]:
                ind["value"] = ind["value"][:12] + "…"  # keyed hash only; never the identifier itself
        a = conn.execute("SELECT * FROM assessments WHERE item_id=?", (item_id,)).fetchone()
        d["assessment"] = {k: (json.loads(a[k]) if k.endswith("_json") else a[k]) for k in a.keys()} if a else None
        d["versions"] = [dict(x) for x in conn.execute(
            "SELECT seen_at, content_hash, capture_sha FROM item_versions WHERE item_id=? ORDER BY id", (item_id,))]
        d["captures"] = [dict(x) for x in conn.execute(
            "SELECT fetched_at, status, sha256, elapsed_s, outcome, isolation_id FROM captures WHERE url=? "
            "ORDER BY id DESC LIMIT 20", (d["url"],))]
        return d

    @app.get("/api/descriptors")
    async def descriptors(limit: int = 50):
        return [dict(r) for r in conn.execute(
            "SELECT * FROM descriptor_observations ORDER BY id DESC LIMIT ?", (min(limit, 500),))]

    @app.get("/api/audit/verify")
    async def audit_verify():
        return ctx.audit.verify()

    @app.get("/api/audit/tail")
    async def audit_tail(limit: int = 30):
        return [dict(r) for r in conn.execute(
            "SELECT seq, ts, actor, action, target, decision, detail_json, hash FROM audit_log ORDER BY seq DESC LIMIT ?",
            (min(limit, 200),))]

    # ---------- M4: deep lane ----------
    def _j(row, *fields):
        d = dict(row)
        for f in fields:
            d[f.removesuffix("_json")] = json.loads(d.pop(f) or "null")
        return d

    @app.get("/api/items/{item_id}/deep")
    async def item_deep(item_id: int):
        r = conn.execute("SELECT * FROM deep_assessments WHERE item_id=?", (item_id,)).fetchone()
        if not r:
            raise HTTPException(404, "not yet assessed by the deep lane")
        return _j(r, "authenticity_json", "attribution_json", "money_json", "correlation_json", "reasons_json")

    @app.get("/api/actors")
    async def actors():
        return [_j(r, "members_json") for r in conn.execute("SELECT * FROM actors ORDER BY id")]

    @app.get("/api/links")
    async def links(min_p: float = 0.35):
        out = []
        for r in conn.execute("SELECT * FROM account_links WHERE probability >= ? ORDER BY probability DESC", (min_p,)):
            d = _j(r, "evidence_json")
            for side in ("a", "b"):
                acc = conn.execute("SELECT alias, source_id FROM accounts WHERE id=?", (r[side],)).fetchone()
                d[f"{side}_alias"], d[f"{side}_source"] = (acc["alias"], acc["source_id"]) if acc else (None, None)
            out.append(d)
        return out

    @app.get("/api/wallets/{address}")
    async def wallet(address: str):
        w = conn.execute("SELECT * FROM wallets WHERE address=?", (address,)).fetchone()
        if not w:
            raise HTTPException(404)
        d = dict(w)
        if w["cluster_id"]:
            c = conn.execute("SELECT * FROM wallet_clusters WHERE id=?", (w["cluster_id"],)).fetchone()
            d["cluster"] = _j(c, "addresses_json", "evidence_json", "flags_json", "exposure_json") if c else None
        d["seen_in_items"] = [dict(r) for r in conn.execute(
            "SELECT i.id, i.title, i.source_id, i.author FROM indicators ind JOIN items i ON i.id=ind.item_id "
            "WHERE ind.value=?", (address,))]
        return d

    def _cluster_view(c) -> dict:
        flags_raw = json.loads(c["flags_json"] or "[]")
        seeds = [r[0] for r in conn.execute("SELECT address FROM wallets WHERE cluster_id=?", (c["id"],))]
        seen = []
        if seeds:
            seen = [dict(r) for r in conn.execute(
                f"SELECT DISTINCT i.id, i.title, i.author, i.source_id FROM indicators ind JOIN items i ON i.id=ind.item_id "
                f"WHERE ind.kind='wallet_btc' AND ind.value IN ({','.join('?' * len(seeds))}) ORDER BY i.first_seen", seeds)]
        return {"id": c["id"], "chain": c["chain"], "size": c["size"], "label": c["label"],
                "addresses": json.loads(c["addresses_json"] or "[]"), "exposure": json.loads(c["exposure_json"] or "[]"),
                "flags": [f for f in flags_raw if isinstance(f, str)],
                "peel_chains": next((f["peel_chains"] for f in flags_raw if isinstance(f, dict)), []),
                "evidence": json.loads(c["evidence_json"] or "[]"), "seeds": seeds, "seen_in_items": seen,
                "updated_at": c["updated_at"]}

    @app.get("/api/clusters")
    async def clusters():
        return [_cluster_view(c) for c in conn.execute("SELECT * FROM wallet_clusters ORDER BY size DESC")]

    @app.get("/api/clusters/{cluster_id}/ledger")
    async def cluster_ledger(cluster_id: str):
        c = conn.execute("SELECT * FROM wallet_clusters WHERE id=?", (cluster_id,)).fetchone()
        if not c:
            raise HTTPException(404)
        view = _cluster_view(c)
        members = set(view["addresses"])
        entity_of = {d: e["entity"] for e in view["exposure"] for d in e["deposits"]}
        peel_txids = {s["txid"] for chain in view["peel_chains"] for s in chain.get("steps", [])}
        entries = []
        for r in conn.execute("SELECT raw_json FROM chain_txs"):
            tx = json.loads(r["raw_json"])
            ins = [v["prevout"] for v in tx.get("vin", []) if not v.get("is_coinbase") and v.get("prevout")]
            outs = [o for o in tx.get("vout", []) if o.get("scriptpubkey_address")]
            debit = sum(p["value"] for p in ins if p["scriptpubkey_address"] in members)
            credit = sum(o["value"] for o in outs if o["scriptpubkey_address"] in members)
            if not debit and not credit:
                continue
            to_entity = next((entity_of[o["scriptpubkey_address"]] for o in outs if o["scriptpubkey_address"] in entity_of), None)
            external = [o for o in outs if o["scriptpubkey_address"] not in members]
            if to_entity:
                particulars = f"Paid to {to_entity}"
            elif debit and credit and not external:
                particulars = "Internal transfer (consolidation or change)"
            elif credit and not debit:
                particulars = "Received from an outside address"
            else:
                particulars = "Sent to an outside address"
            fee = sum(p["value"] for p in ins) - sum(o.get("value", 0) for o in tx.get("vout", [])) if debit else 0
            entries.append({"txid": tx["txid"], "height": tx["status"]["block_height"],
                            "time": tx["status"]["block_time"], "debit_sats": debit, "credit_sats": credit,
                            "fee_sats": max(fee, 0), "external_sats": sum(o["value"] for o in external),
                            "entity_sats": sum(o["value"] for o in outs if o["scriptpubkey_address"] in entity_of),
                            "particulars": particulars, "entity": to_entity, "peel": tx["txid"] in peel_txids})
        entries.sort(key=lambda e: (e["height"], e["txid"]))
        balance = 0
        for e in entries:
            balance += e["credit_sats"] - e["debit_sats"]
            e["balance_sats"] = balance
        return {"cluster": view, "entries": entries,
                "note": "Heuristic clustering: an investigative lead, not proof of common ownership."}

    @app.get("/api/incidents")
    async def incidents():
        return [_j(r, "item_ids_json", "sources_json", "summary_json")
                for r in conn.execute("SELECT * FROM incidents ORDER BY last_seen DESC")]

    @app.get("/api/graph")
    async def graph(focus: str, depth: int = 2):
        return ctx.nexus.subgraph(focus, depth=min(max(depth, 1), 4))

    @app.get("/api/path")
    async def path(a: str, b: str):
        return {"a": a, "b": b, "steps": ctx.nexus.evidence_path(a, b)}

    @app.get("/api/deeplane")
    async def deeplane_status():
        return ctx.deep.last_pass if getattr(ctx, "deep", None) else {}

    # ---------- M5: evidence ----------
    @app.post("/api/items/{item_id}/evidence")
    async def build_evidence(item_id: int):
        codex = getattr(ctx, "codex", None)
        if not codex:
            raise HTTPException(503, "evidence builder not running")
        try:
            result = await codex.build(item_id, requested_by="dashboard-operator")
        except KeyError:
            raise HTTPException(404, "item not found")
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return {**{k: v for k, v in result.items() if k != "path"}, "download": f"/api/evidence/{result['pack_id']}.zip"}

    @app.get("/api/evidence")
    async def list_packs():
        return [_j(r, "summary_json") for r in conn.execute(
            "SELECT id, created_at, item_id, alert_id, created_by, manifest_sha256, zip_sha256, summary_json "
            "FROM evidence_packs ORDER BY created_at DESC")]

    @app.get("/api/evidence/{pack_id}.zip")
    async def download_pack(pack_id: str):
        if not PACK_ID_RE.match(pack_id):
            raise HTTPException(404)
        row = conn.execute("SELECT path FROM evidence_packs WHERE id=?", (pack_id,)).fetchone()
        if not row or not Path(row["path"]).exists():
            raise HTTPException(404)
        return FileResponse(row["path"], media_type="application/zip", filename=f"{pack_id}.zip")

    @app.get("/api/tabularium")
    async def tabularium_status():
        counts = {r[0]: r[1] for r in conn.execute("SELECT status, COUNT(*) FROM merkle_batches GROUP BY status")}
        last = conn.execute("SELECT id, created_at, root, size, status, tsa_gen_time FROM merkle_batches "
                            "ORDER BY id DESC LIMIT 1").fetchone()
        sealed = conn.execute("SELECT COUNT(*) FROM batch_leaves WHERE kind='capture'").fetchone()[0]
        return {"batches_by_status": counts, "captures_sealed": sealed, "last_batch": dict(last) if last else None}

    # ---------- M7: readiness ----------
    @app.post("/api/lex/drill")
    async def drill_lex():
        onion = getattr(ctx, "forum_onion", None)
        if not onion:
            raise HTTPException(503, "no forum source configured")
        result = lex_drill(ctx.lex, onion, actor="dashboard-operator")
        ctx.bus.publish({"type": "lex_drill", "passed": result["passed"]})
        return result

    def _records(folder: str, limit: int) -> list[dict]:
        d = PATHS.var / folder
        if not d.exists():
            return []
        out = []
        for f in sorted(d.glob("*.json"), reverse=True)[:limit]:
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return out

    @app.get("/api/rehearsals")
    async def rehearsals(limit: int = 12):
        return _records("rehearsals", min(limit, 50))

    @app.get("/api/drills")
    async def drills(limit: int = 20):
        return _records("drills", min(limit, 50))

    @app.post("/api/kill")
    async def kill(req: KillRequest):
        ctx.lex.engage_kill("dashboard", req.reason)
        if hasattr(ctx.aquila, "sever"):  # cut requests already on the wire; Lex refuses every new one
            await ctx.aquila.sever()
        ctx.bus.publish({"type": "kill_switch", "engaged": True, "reason": req.reason})
        return {"kill_engaged": True}

    @app.post("/api/resume")
    async def resume():
        ctx.lex.release_kill("dashboard")
        ctx.bus.publish({"type": "kill_switch", "engaged": False})
        return {"kill_engaged": False}

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        if not origin_ok(socket.headers.get("origin")):
            await socket.close(code=1008)  # policy violation: foreign page trying to read the alert stream
            return
        await socket.accept()
        q = ctx.bus.subscribe()
        try:
            while True:
                event = await q.get()
                await socket.send_text(json.dumps(event, default=str))
        except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
            pass
        finally:
            ctx.bus.unsubscribe(q)

    return app
