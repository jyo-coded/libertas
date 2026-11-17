"""Central configuration. Phase 0 runs on one laptop in development mode (strict allowlist)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAR = Path(os.environ.get("LIBERTAS_VAR", str(ROOT / "var")))
DATA = ROOT / "data"


def _default_tor_exe() -> str:
    env = os.environ.get("LIBERTAS_TOR_EXE")
    if env:
        return env
    candidate = Path.home() / "Desktop" / "Tor Browser" / "Browser" / "TorBrowser" / "Tor" / "tor.exe"
    return str(candidate) if candidate.exists() else "tor"


@dataclass(frozen=True)
class Paths:
    var: Path = VAR
    db: Path = VAR / "libertas.db"
    quarantine: Path = VAR / "quarantine"
    kill_file: Path = VAR / "KILL"
    secret: Path = VAR / "secret.key"
    blocklist_md5: Path = VAR / "blocklist_md5.txt"
    tor_client: Path = VAR / "tor" / "client"
    run: Path = VAR / "run"
    shadownet: Path = VAR / "shadownet"
    shadownet_registry: Path = VAR / "shadownet" / "registry.json"
    evidence: Path = VAR / "evidence"
    signing_key: Path = VAR / "keys" / "evidence_signing_ed25519.pem"


@dataclass(frozen=True)
class Settings:
    mode: str = os.environ.get("LIBERTAS_MODE", "development")
    tor_exe: str = _default_tor_exe()
    socks_host: str = "127.0.0.1"
    socks_port: int = int(os.environ.get("LIBERTAS_SOCKS_PORT", "19050"))
    control_port: int = int(os.environ.get("LIBERTAS_CONTROL_PORT", "19051"))
    api_host: str = "127.0.0.1"
    api_port: int = int(os.environ.get("LIBERTAS_API_PORT", "8700"))
    # Headers match Tor Browser on Windows (Firefox ESR 153 engine), except Accept-Encoding: we only
    # advertise encodings we can decompress ourselves under a hard cap (no br/zstd).
    user_agent: str = os.environ.get(
        "LIBERTAS_UA", "Mozilla/5.0 (Windows NT 10.0; rv:153.0) Gecko/20100101 Firefox/153.0")
    # zero-execution and resource caps (blueprint §11.14)
    max_response_bytes: int = 2_000_000
    max_compressed_bytes: int = 2_000_000
    request_timeout_s: float = 60.0
    connect_timeout_s: float = 60.0
    max_redirects: int = 3
    max_concurrent_fetches: int = 6
    max_queue: int = 500
    # scheduling (Aquila)
    pulse_interval_s: float = float(os.environ.get("LIBERTAS_PULSE_S", "20"))
    pulse_jitter: float = 0.2
    revisit_interval_s: float = float(os.environ.get("LIBERTAS_REVISIT_S", "45"))
    revisit_window_s: float = 6 * 3600.0
    pulsus_interval_s: float = float(os.environ.get("LIBERTAS_PULSUS_S", "300"))
    # alerting
    alert_min_score: float = 35.0
    telegram_bot_token: str = os.environ.get("LIBERTAS_TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.environ.get("LIBERTAS_TELEGRAM_CHAT_ID", "")
    # evidence (Tabularium / Codex). Only a SHA-256 Merkle root is ever sent to the timestamp authority.
    tsa_url: str = os.environ.get("LIBERTAS_TSA_URL", "https://freetsa.org/tsr")
    tsa_enabled: bool = os.environ.get("LIBERTAS_TSA", "1") == "1"
    seal_interval_s: float = float(os.environ.get("LIBERTAS_SEAL_S", "120"))
    unit_name: str = os.environ.get("LIBERTAS_UNIT", "Cyber Crime Wing (demo unit)")


# Legitimate onions measured in blueprint §3.3. Allowed for benchmarking only (Gate B).
BENCHMARK_ONIONS = {
    "2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid",  # Tor Project
    "juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd",  # Ahmia
    "duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad",  # DuckDuckGo
    "bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd",  # BBC
    "sdolvtfhatvsysc6l34d65ymdwxcujausv7k5jk4cy5ttzhjoi6fzvyd",  # SecureDrop directory
}

PATHS = Paths()
SETTINGS = Settings()
