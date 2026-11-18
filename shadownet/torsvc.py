"""Publish ShadowNet's sites as real onion services with ShadowNet's own tor instance.

Private sites use Tor client authorisation (restricted discovery), so only holders of the Libertas client key
can even fetch their descriptors' inner layer and connect. ShadowLock stays public with proof-of-work armed,
which is realistic for a leak site and lets Pulsus show descriptor intelligence on a site we control.
"""
from __future__ import annotations

import asyncio
import base64
import json
import shutil
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from libertas.common.timeutil import now_iso
from libertas.config import PATHS, SETTINGS
from libertas.speculatores.torproc import list_modules, start_tor, write_torrc

SITES = [
    {"id": "kaal-forum", "kind": "forum", "name": "Kaal Forum (SIM)", "port": 8601, "private": True,
     "adapter": "shadownet_forum", "pow": False},
    {"id": "sona-bazaar", "kind": "market", "name": "Sona Bazaar (SIM)", "port": 8602, "private": True,
     "adapter": "shadownet_market", "pow": False},
    {"id": "shadowlock", "kind": "leakblog", "name": "ShadowLock leak blog (SIM)", "port": 8603, "private": False,
     "adapter": "shadownet_leakblog", "pow": True},
    {"id": "deaddrop", "kind": "paste", "name": "DeadDrop pastes (SIM)", "port": 8604, "private": True,
     "adapter": "shadownet_paste", "pow": False},
]
PANEL_PORT = 8600
# the heartbeat canary: a separate public onion whose page changes every minute (blueprint section 10)
HEARTBEAT = {"id": "heartbeat", "port": 8606}
CONTROL_PORT = 19061
BASE = PATHS.shadownet / "tor"


def _b32(raw: bytes) -> str:
    return base64.b32encode(raw).decode().rstrip("=")


def ensure_client_auth() -> dict:
    path = PATHS.shadownet / "client_auth.json"
    if path.exists():
        return json.loads(path.read_text())
    key = X25519PrivateKey.generate()
    priv = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    auth = {"name": "libertas", "private_key_b32": _b32(priv), "public_key_b32": _b32(pub), "created_at": now_iso()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(auth, indent=2))
    return auth


def _prepare_dirs(auth: dict) -> None:
    for site in SITES:
        hs = BASE / f"hs_{site['id']}"
        hs.mkdir(parents=True, exist_ok=True)
        clients = hs / "authorized_clients"
        if site["private"]:
            clients.mkdir(exist_ok=True)
            (clients / "libertas.auth").write_text(f"descriptor:x25519:{auth['public_key_b32']}\n")
        elif clients.exists():
            shutil.rmtree(clients)
    (BASE / f"hs_{HEARTBEAT['id']}").mkdir(parents=True, exist_ok=True)


def _torrc(pow_supported: bool) -> list[str]:
    lines = [f"DataDirectory {BASE.as_posix()}", "SocksPort 0", f"ControlPort 127.0.0.1:{CONTROL_PORT}",
             "CookieAuthentication 1", f"Log notice file {(BASE / 'notice.log').as_posix()}"]
    for site in SITES:
        lines += [f"HiddenServiceDir {(BASE / ('hs_' + site['id'])).as_posix()}",
                  f"HiddenServicePort 80 127.0.0.1:{site['port']}"]
        if site["pow"] and pow_supported:
            lines.append("HiddenServicePoWDefensesEnabled 1")
    lines += [f"HiddenServiceDir {(BASE / ('hs_' + HEARTBEAT['id'])).as_posix()}",
              f"HiddenServicePort 80 127.0.0.1:{HEARTBEAT['port']}"]
    return lines


async def start_service_tor(log=print):
    auth = ensure_client_auth()
    _prepare_dirs(auth)
    pow_supported = list_modules(SETTINGS.tor_exe).get("pow", False)
    torrc = write_torrc(BASE / "torrc", _torrc(pow_supported))
    proc = start_tor(SETTINGS.tor_exe, torrc, BASE / "tor-stdout.log")
    log(f"ShadowNet tor started (pid {proc.pid}); PoW module available: {pow_supported}")
    onions: dict[str, str] = {}
    for _ in range(120):
        for site in SITES + [HEARTBEAT]:
            host = BASE / f"hs_{site['id']}" / "hostname"
            if host.exists() and site["id"] not in onions:
                onions[site["id"]] = host.read_text().strip().removesuffix(".onion")
        if len(onions) == len(SITES) + 1:
            break
        if proc.poll() is not None:
            raise RuntimeError(f"ShadowNet tor exited early; see {BASE / 'notice.log'}")
        await asyncio.sleep(0.5)
    if len(onions) != len(SITES) + 1:
        raise RuntimeError("onion hostnames were not created in time")
    registry = {"generated_at": now_iso(), "simulation": True, "control_port": CONTROL_PORT,
                "cookie": (BASE / "control_auth_cookie").as_posix(), "pow_supported": pow_supported,
                "client_auth": {"name": auth["name"], "private_key_b32": auth["private_key_b32"]},
                "sites": [{**{k: s[k] for k in ("id", "kind", "name", "private", "adapter")},
                           "pow": s["pow"] and pow_supported, "onion": onions[s["id"]]} for s in SITES],
                "heartbeat": {"onion": onions[HEARTBEAT["id"]], "path": "/", "period_s": 60}}
    PATHS.shadownet_registry.write_text(json.dumps(registry, indent=2))
    return proc, registry
