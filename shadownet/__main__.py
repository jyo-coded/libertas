"""ShadowNet CLI.

  python -m shadownet up [--reseed]   start the 4 sites, the control panel and the onion services
  python -m shadownet seed            reset and reseed the fictional world
  python -m shadownet status          print the registry (onion addresses)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import uvicorn

from libertas.common.priority import lower_priority
from libertas.config import PATHS
from libertas.speculatores.torproc import wait_bootstrapped

from .adversary import Adversary, heartbeat_app, install, scheduler
from .chain import build_ledger, chain_app
from .panel import panel_app
from .sites import SITE_APPS
from .store import Store
from .torsvc import HEARTBEAT, PANEL_PORT, SITES, start_service_tor
from .world import seed

CHAIN_PORT = 8605


def _store() -> Store:
    return Store(PATHS.shadownet / "shadownet.db")


async def run_up(reseed: bool) -> None:
    lower_priority()
    store = _store()
    if reseed or store.is_empty():
        print("seeding fictional world:", seed(store), flush=True)
    proc, registry = await start_service_tor(log=lambda m: print(m, flush=True))
    ledger = build_ledger()
    registry["chain_api"] = f"http://127.0.0.1:{CHAIN_PORT}/api"
    registry["chain_labels"] = ledger.labels
    PATHS.shadownet_registry.write_text(json.dumps(registry, indent=2))
    for s in registry["sites"]:
        print(f"  {s['name']:<28} http://{s['onion']}.onion  ({'private' if s['private'] else 'public'})", flush=True)
    print(f"  heartbeat canary             http://{registry['heartbeat']['onion']}.onion/  (public, changes every minute)",
          flush=True)
    print(f"  control panel (local only)    http://127.0.0.1:{PANEL_PORT}/", flush=True)
    print(f"  ShadowChain (simulated BTC)   http://127.0.0.1:{CHAIN_PORT}/  ({len(ledger.txs)} transactions)", flush=True)

    async def report_bootstrap():
        try:
            secs = await wait_bootstrapped(registry["control_port"], registry["cookie"],
                                           log=lambda m: print("shadownet " + m, flush=True))
            print(f"ShadowNet tor bootstrapped in {secs}s; descriptors publish shortly after", flush=True)
        except TimeoutError as exc:
            print(f"warning: {exc}", flush=True)

    asyncio.create_task(report_bootstrap())
    adv = Adversary()
    site_apps = {}
    for s in SITES:
        app = SITE_APPS[s["kind"]](store)
        install(app, s["kind"], adv)
        site_apps[s["id"]] = (app, s["port"])

    def make_server(app, port):
        return uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                             server_header=False, access_log=False))

    loop = asyncio.get_running_loop()
    live: dict[str, uvicorn.Server] = {}
    tasks: list[asyncio.Task] = []

    def start_site(site_id: str) -> None:
        srv = make_server(*site_apps[site_id])
        live[site_id] = srv
        tasks.append(loop.create_task(srv.serve()))

    def set_offline(offline: bool) -> None:
        """Adversary 'offline': DeadDrop's web server stops behind its onion address, then comes back."""
        def apply():
            if offline and "deaddrop" in live:
                live.pop("deaddrop").should_exit = True
                print("adversary: DeadDrop server taken offline", flush=True)
            elif not offline and "deaddrop" not in live:
                start_site("deaddrop")
                print("adversary: DeadDrop server back online", flush=True)
        loop.call_soon_threadsafe(apply)

    adv.on_offline_change = set_offline
    for site_id in site_apps:
        start_site(site_id)
    for app, port in ((panel_app(store, adv), PANEL_PORT), (chain_app(ledger), CHAIN_PORT),
                      (heartbeat_app(), HEARTBEAT["port"])):
        tasks.append(loop.create_task(make_server(app, port).serve()))
    tasks.append(loop.create_task(scheduler(store, adv, log=lambda m: print(m, flush=True))))
    try:
        while True:  # sites may stop and restart (adversary 'offline'), so wait on the long-lived pieces
            await asyncio.sleep(3600)
    finally:
        for t in tasks:
            t.cancel()
        proc.terminate()


def main() -> None:
    ap = argparse.ArgumentParser(prog="shadownet")
    sub = ap.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("up")
    up.add_argument("--reseed", action="store_true")
    sub.add_parser("seed")
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "seed":
        print(seed(_store()))
    elif args.cmd == "status":
        print(PATHS.shadownet_registry.read_text() if PATHS.shadownet_registry.exists() else "not started yet")
    else:
        try:
            asyncio.run(run_up(args.reseed))
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
