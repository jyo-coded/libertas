"""SQLite system of record for Phase 0 (WAL mode). Swappable for PostgreSQL later."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import PATHS

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
    id TEXT PRIMARY KEY, name TEXT, kind TEXT, onion TEXT, adapter TEXT, priority INTEGER DEFAULT 5,
    enabled INTEGER DEFAULT 1, added_at TEXT, simulated INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS descriptor_observations(
    id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, onion TEXT, observed_at TEXT, result TEXT,
    seconds REAL, hsdirs_asked INTEGER, intro_points INTEGER, pow_enabled INTEGER, pow_effort INTEGER,
    single_onion INTEGER, private INTEGER, error TEXT);

CREATE TABLE IF NOT EXISTS captures(
    id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, url TEXT, final_url TEXT, fetched_at TEXT,
    status INTEGER, content_type TEXT, bytes INTEGER, sha256 TEXT, elapsed_s REAL, isolation_id TEXT,
    headers_json TEXT, outcome TEXT, note TEXT);
CREATE INDEX IF NOT EXISTS ix_captures_sha ON captures(sha256);

CREATE TABLE IF NOT EXISTS items(
    id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, item_key TEXT, kind TEXT, url TEXT, title TEXT,
    author TEXT, body_text TEXT, posted_at TEXT, first_seen TEXT, last_seen TEXT, last_checked TEXT,
    deleted_at TEXT, content_hash TEXT, first_capture_sha TEXT, last_capture_sha TEXT, extra_json TEXT,
    detection_lag_s REAL, UNIQUE(source_id, item_key));

CREATE TABLE IF NOT EXISTS item_versions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, seen_at TEXT, content_hash TEXT,
    capture_sha TEXT, title TEXT, body_text TEXT);

CREATE TABLE IF NOT EXISTS indicators(
    id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, kind TEXT, value TEXT, display TEXT,
    valid INTEGER, sensitive INTEGER DEFAULT 0, UNIQUE(item_id, kind, value));
CREATE INDEX IF NOT EXISTS ix_indicators_value ON indicators(kind, value);

CREATE TABLE IF NOT EXISTS assessments(
    item_id INTEGER PRIMARY KEY, assessed_at TEXT, method TEXT, categories_json TEXT, orgs_json TEXT,
    sectors_json TEXT, score REAL, severity TEXT, factors_json TEXT, reasons_json TEXT);

CREATE TABLE IF NOT EXISTS alerts(
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, updated_at TEXT, item_id INTEGER UNIQUE,
    source_id TEXT, severity TEXT, score REAL, title TEXT, summary TEXT, categories_json TEXT,
    orgs_json TEXT, sectors_json TEXT, factors_json TEXT, status TEXT DEFAULT 'new', provisional INTEGER DEFAULT 1,
    detection_lag_s REAL, deleted INTEGER DEFAULT 0, notes TEXT DEFAULT '');

-- ---------- M4 deep lane ----------
CREATE TABLE IF NOT EXISTS accounts(
    id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, alias TEXT, first_seen TEXT, last_seen TEXT,
    items INTEGER DEFAULT 0, style_chars INTEGER DEFAULT 0, actor_id INTEGER, UNIQUE(source_id, alias));

CREATE TABLE IF NOT EXISTS account_links(
    a INTEGER, b INTEGER, probability REAL, truth TEXT, evidence_json TEXT, updated_at TEXT, PRIMARY KEY(a, b));

CREATE TABLE IF NOT EXISTS actors(
    id INTEGER PRIMARY KEY AUTOINCREMENT, anchor TEXT UNIQUE, label TEXT, members_json TEXT, confidence REAL,
    truth TEXT, created_at TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS wallets(
    address TEXT PRIMARY KEY, chain TEXT, cluster_id TEXT, received_sats INTEGER, sent_sats INTEGER,
    tx_count INTEGER, label TEXT, analysed_at TEXT);

CREATE TABLE IF NOT EXISTS wallet_clusters(
    id TEXT PRIMARY KEY, chain TEXT, addresses_json TEXT, size INTEGER, evidence_json TEXT, flags_json TEXT,
    exposure_json TEXT, label TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS chain_txs(txid TEXT PRIMARY KEY, chain TEXT, raw_json TEXT, fetched_at TEXT);

CREATE TABLE IF NOT EXISTS incidents(
    id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, title TEXT, org TEXT, first_seen TEXT, last_seen TEXT,
    item_ids_json TEXT, sources_json TEXT, summary_json TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS deep_assessments(
    item_id INTEGER PRIMARY KEY, assessed_at TEXT, method TEXT, authenticity_json TEXT, attribution_json TEXT,
    money_json TEXT, correlation_json TEXT, score REAL, severity TEXT, reasons_json TEXT, latency_s REAL);

-- ---------- M5 evidence ----------
CREATE TABLE IF NOT EXISTS merkle_batches(
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, root TEXT, size INTEGER, audit_seq INTEGER,
    audit_head TEXT, signature TEXT, status TEXT, tsa_url TEXT, tsr BLOB, tsa_gen_time TEXT, tsa_info_json TEXT,
    error TEXT);

CREATE TABLE IF NOT EXISTS batch_leaves(
    batch_id INTEGER, leaf_index INTEGER, kind TEXT, ref INTEGER, leaf_hash TEXT, PRIMARY KEY(batch_id, leaf_index));
CREATE INDEX IF NOT EXISTS ix_batch_leaves_ref ON batch_leaves(kind, ref);

CREATE TABLE IF NOT EXISTS evidence_packs(
    id TEXT PRIMARY KEY, created_at TEXT, item_id INTEGER, alert_id INTEGER, created_by TEXT, manifest_sha256 TEXT,
    zip_sha256 TEXT, path TEXT, summary_json TEXT);

CREATE TABLE IF NOT EXISTS audit_log(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT, target TEXT, decision TEXT,
    detail_json TEXT, prev_hash TEXT, hash TEXT);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or PATHS.db)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn
