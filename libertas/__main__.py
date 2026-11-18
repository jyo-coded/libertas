"""Libertas CLI.

  python -m libertas up            start the Tor client, Pulsus, Aquila, the pipeline and the API
  python -m libertas kill [-r why] engage the kill switch (all collection stops at once)
  python -m libertas resume        release the kill switch
  python -m libertas status        print a summary from the database
  python -m libertas verify-audit  check the hash chain of the audit log
  python -m libertas drill-lex     ask the crawler to cross the line (log in, leave Tor, download) and show it refuses
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
from types import SimpleNamespace

import uvicorn

from . import db
from .api.app import create_app
from .common.priority import lower_priority
from .common.timeutil import now_iso
from .config import BENCHMARK_ONIONS, DATA, PATHS, SETTINGS
from .interpres.indicators import Extractor
from .interpres.watchlist import Watchlist
from .janus.quarantine import Quarantine
from .lex.audit import AuditLog
from .codex import EvidencePackBuilder
from .deeplane import DeepLane
from .tabularium import Signer, Tabularium
from .lex.policy import Lex
from .moneta import EsploraProvider, Moneta
from .nexus import Nexus
from .pipeline import Pipeline
from .stilus import Stilus
from .speculatores.aquila import Aquila, Source
from .speculatores.pulsus import Pulsus
from .speculatores.torproc import start_tor, wait_bootstrapped, write_torrc
from .vigiles.alerts import Vigiles
from .vigiles.bus import Bus


def log(msg: str) -> None:
    print(f"[libertas] {msg}", flush=True)


def write_pid(pid: int) -> None:
    """The failure drills read this to stop the Tor client on purpose."""
    PATHS.run.mkdir(parents=True, exist_ok=True)
    (PATHS.run / "tor_client.pid").write_text(str(pid))


def secret_key() -> bytes:
    if not PATHS.secret.exists():
        PATHS.secret.parent.mkdir(parents=True, exist_ok=True)
        PATHS.secret.write_bytes(secrets.token_bytes(32))
    return PATHS.secret.read_bytes()


def load_sources(conn) -> tuple[list[Source], dict]:
    if not PATHS.shadownet_registry.exists():
        raise SystemExit("ShadowNet registry not found. Start ShadowNet first:  python -m shadownet up")
    reg = json.loads(PATHS.shadownet_registry.read_text())
    sources = [Source(s["id"], s["name"], s["kind"], s["onion"], s["adapter"], True, s["private"]) for s in reg["sites"]]
    for s in sources:
        conn.execute(
            "INSERT INTO sources(id, name, kind, onion, adapter, priority, enabled, added_at, simulated) "
            "VALUES (?,?,?,?,?,1,1,?,1) ON CONFLICT(id) DO UPDATE SET name=excluded.name, onion=excluded.onion, "
            "adapter=excluded.adapter", (s.id, s.name, s.kind, s.onion, s.adapter, now_iso()))
    return sources, reg


def write_client_auth(reg: dict):
    auth_dir = PATHS.tor_client / "onion_auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    for s in reg["sites"]:
        f = auth_dir / f"{s['id']}.auth_private"
        if s["private"]:
            f.write_text(f"{s['onion']}:descriptor:x25519:{reg['client_auth']['private_key_b32']}\n")
        elif f.exists():
            f.unlink()
    return auth_dir


async def up() -> None:
    lower_priority()
    conn = db.connect()
    audit = AuditLog(conn)
    sources, reg = load_sources(conn)
    allow = {s.onion for s in sources} | BENCHMARK_ONIONS
    heartbeat_onion = (reg.get("heartbeat") or {}).get("onion")
    if heartbeat_onion:
        allow.add(heartbeat_onion)
    lex = Lex(audit, mode=SETTINGS.mode, kill_file=PATHS.kill_file, allowlist=allow, blocklist_file=PATHS.blocklist_md5)
    audit.append("operator", "startup", "libertas", "ok",
                 {"mode": SETTINGS.mode, "sources": [s.id for s in sources], "allowlist_size": len(allow)})
    auth_dir = write_client_auth(reg)
    torrc = write_torrc(PATHS.tor_client / "torrc", [
        f"DataDirectory {PATHS.tor_client.as_posix()}",
        f"SocksPort {SETTINGS.socks_host}:{SETTINGS.socks_port} IsolateSOCKSAuth",
        f"ControlPort 127.0.0.1:{SETTINGS.control_port}",
        "CookieAuthentication 1",
        f"ClientOnionAuthDir {auth_dir.as_posix()}",
        f"Log notice file {(PATHS.tor_client / 'notice.log').as_posix()}",
        "SafeLogging 1",
    ])
    tor = {"proc": start_tor(SETTINGS.tor_exe, torrc, PATHS.tor_client / "tor-stdout.log"), "restarts": 0,
           "state": "bootstrapping", "last_restart_at": None, "last_outage_s": None}
    write_pid(tor["proc"].pid)
    log(f"tor client started (pid {tor['proc'].pid}); bootstrapping")
    cookie = PATHS.tor_client / "control_auth_cookie"
    secs = await wait_bootstrapped(SETTINGS.control_port, cookie, log=log)
    tor["state"], tor["bootstrap_s"] = "running", secs
    log(f"tor client bootstrapped in {secs}s")
    pulsus = await Pulsus(SETTINGS.control_port, cookie).start()
    bus = Bus()
    vigiles = Vigiles(conn, audit, bus, SETTINGS, log=log)
    secret = secret_key()
    quarantine = Quarantine(PATHS.quarantine)
    pipeline = Pipeline(conn, audit, quarantine, Watchlist.load(DATA / "watchlist.json"),
                        {True: Extractor(secret, simulation=True), False: Extractor(secret, simulation=False)},
                        vigiles, bus, log=log)
    aquila = Aquila(conn, lex, SETTINGS, pipeline, sources, pulsus=pulsus, log=log, heartbeat_onion=heartbeat_onion)
    # deep lane: chain data comes from ShadowChain in Phase 0 (a self-hosted Esplora node in production)
    provider = EsploraProvider(reg["chain_api"]) if reg.get("chain_api") else None
    moneta = Moneta(conn, provider, reg.get("chain_labels", [])) if provider else None
    nexus = Nexus(conn)
    deep = DeepLane(conn, audit, bus, vigiles, Stilus(conn), moneta, nexus, log=log)
    pipeline.deep = deep
    # evidence: Merkle batches signed with the Libertas key, timestamped by an RFC 3161 TSA (only digests leave)
    signer = Signer(PATHS.signing_key)
    tabularium = Tabularium(conn, audit, signer, SETTINGS, log=log)
    codex = EvidencePackBuilder(conn, audit, quarantine, tabularium, signer, SETTINGS, PATHS.evidence)
    log(f"evidence signing key (Ed25519) {signer.fingerprint[:16]}…; timestamps: "
        f"{SETTINGS.tsa_url if SETTINGS.tsa_enabled else 'disabled'}; sealing every {SETTINGS.seal_interval_s:.0f}s")
    forum_onion = next((s.onion for s in sources if s.kind == "forum"), sources[0].onion)
    ctx = SimpleNamespace(conn=conn, audit=audit, lex=lex, bus=bus, vigiles=vigiles, aquila=aquila, settings=SETTINGS,
                          nexus=nexus, deep=deep, tabularium=tabularium, codex=codex, tor=tor, forum_onion=forum_onion)

    async def tor_watchdog() -> None:
        """If the Tor client dies (crash, kill, sleep/resume), restart it and record the outage."""
        nonlocal pulsus
        import time as _time
        while True:
            await asyncio.sleep(3)
            if tor["proc"].poll() is None:
                continue
            down_at = _time.monotonic()
            tor["state"] = "down"
            audit.append("operator", "tor_down", "tor-client", "restarting", {"exit_code": tor["proc"].returncode})
            bus.publish({"type": "tor", "state": "down"})
            log("tor client exited; restarting it")
            tor["proc"] = start_tor(SETTINGS.tor_exe, torrc, PATHS.tor_client / "tor-stdout.log")
            write_pid(tor["proc"].pid)
            try:
                await wait_bootstrapped(SETTINGS.control_port, cookie, log=log)
                try:
                    await pulsus.close()
                except Exception:
                    pass
                pulsus = await Pulsus(SETTINGS.control_port, cookie).start()
                aquila.pulsus = pulsus
                tor["restarts"] += 1
                tor["last_restart_at"] = now_iso()
                tor["last_outage_s"] = round(_time.monotonic() - down_at, 1)
                tor["state"] = "running"
                audit.append("operator", "tor_restarted", "tor-client", "ok",
                             {"pid": tor["proc"].pid, "outage_s": tor["last_outage_s"]})
                bus.publish({"type": "tor", "state": "running", "outage_s": tor["last_outage_s"]})
                log(f"tor client back after {tor['last_outage_s']}s (pid {tor['proc'].pid})")
            except TimeoutError as exc:
                log(f"tor restart did not bootstrap: {exc}")
    server = uvicorn.Server(uvicorn.Config(create_app(ctx), host=SETTINGS.api_host, port=SETTINGS.api_port,
                                           log_level="warning", server_header=False))
    log(f"live page and API: http://{SETTINGS.api_host}:{SETTINGS.api_port}/   (kill switch: python -m libertas kill)")

    def report(task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception():
            log(f"background task stopped with an error: {task.exception()!r}")

    collection = asyncio.create_task(aquila.run())
    collection.add_done_callback(report)
    watchdog = asyncio.create_task(tor_watchdog())
    watchdog.add_done_callback(report)
    deep_task = asyncio.create_task(deep.run())
    deep_task.add_done_callback(report)
    seal_task = asyncio.create_task(tabularium.run())
    seal_task.add_done_callback(report)
    try:
        await server.serve()
    finally:
        collection.cancel()
        watchdog.cancel()
        deep_task.cancel()
        seal_task.cancel()
        await tabularium.aclose()
        await aquila.close()
        await pulsus.close()
        if provider:
            await provider.aclose()
        tor["proc"].terminate()
        audit.append("operator", "shutdown", "libertas", "ok", {})


def main() -> None:
    ap = argparse.ArgumentParser(prog="libertas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("up")
    k = sub.add_parser("kill")
    k.add_argument("-r", "--reason", default="operator request")
    sub.add_parser("resume")
    sub.add_parser("status")
    sub.add_parser("verify-audit")
    sub.add_parser("drill-lex")
    args = ap.parse_args()
    if args.cmd == "up":
        try:
            asyncio.run(up())
        except KeyboardInterrupt:
            sys.exit(0)
        return
    conn = db.connect()
    audit = AuditLog(conn)
    lex = Lex(audit, mode=SETTINGS.mode, kill_file=PATHS.kill_file)
    if args.cmd == "kill":
        lex.engage_kill("operator-cli", args.reason)
        print("kill switch ENGAGED: all collection halts within seconds")
    elif args.cmd == "resume":
        lex.release_kill("operator-cli")
        print("kill switch released")
    elif args.cmd == "verify-audit":
        print(json.dumps(audit.verify(), indent=2))
    elif args.cmd == "drill-lex":
        from .lex.drill import run as lex_drill
        sources, _reg = load_sources(conn)
        allow = {s.onion for s in sources} | BENCHMARK_ONIONS
        drill_lex = Lex(audit, mode=SETTINGS.mode, kill_file=PATHS.kill_file, allowlist=allow,
                        blocklist_file=PATHS.blocklist_md5)
        result = lex_drill(drill_lex, next(s.onion for s in sources if s.kind == "forum"), actor="operator-cli")
        for r in result["attempts"]:
            print(f"{'REFUSED' if not r['allowed'] else 'ALLOWED'}  {r['attempt']}\n         {r['method']} "
                  f"{r['url']}\n         reason: {r['reason']}  (audit #{r['audit_seq']})")
        print(f"{result['refused']}/{result['total']} refused; audit chain intact: {result['audit']['ok']}")
    else:
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("sources", "items", "captures", "alerts", "indicators", "descriptor_observations", "audit_log")}
        sev = {r[0]: r[1] for r in conn.execute("SELECT severity, COUNT(*) FROM alerts GROUP BY severity")}
        print(json.dumps({"kill_engaged": lex.kill_engaged(), "counts": counts, "alerts_by_severity": sev,
                          "audit": audit.verify()}, indent=2))


if __name__ == "__main__":
    main()
