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

from .chain import build_ledger, chain_app
from .panel import panel_app
from .sites import SITE_APPS
from .store import Store
from .torsvc import PANEL_PORT, SITES, start_service_tor
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
    configs = [(SITE_APPS[s["kind"]](store), s["port"]) for s in SITES] + [(panel_app(store), PANEL_PORT),
                                                                          (chain_app(ledger), CHAIN_PORT)]
    servers = [uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                             server_header=False, access_log=False)) for app, port in configs]
    try:
        await asyncio.gather(*(srv.serve() for srv in servers))
    finally:
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
