"""ShadowNet's own database (completely separate from Libertas's)."""
from __future__ import annotations

import secrets
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS members(uid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, persona TEXT,
    joined TEXT, pgp TEXT, contact TEXT, signature TEXT, title TEXT);
CREATE TABLE IF NOT EXISTS threads(tid INTEGER PRIMARY KEY AUTOINCREMENT, fid INTEGER, title TEXT, author_uid INTEGER,
    created_at TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS posts(pid INTEGER PRIMARY KEY AUTOINCREMENT, tid INTEGER, author_uid INTEGER, body TEXT,
    created_at TEXT);
CREATE TABLE IF NOT EXISTS vendors(name TEXT PRIMARY KEY, persona TEXT, pgp TEXT, rating REAL, sales INTEGER,
    joined TEXT, wallet TEXT, about TEXT);
CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY AUTOINCREMENT, vendor TEXT, title TEXT, category TEXT,
    price_usd REAL, body TEXT, created_at TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS victims(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, country TEXT, sector TEXT,
    website TEXT, deadline TEXT, status TEXT, data_size TEXT, description TEXT, created_at TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS pastes(id TEXT PRIMARY KEY, title TEXT, author TEXT, body TEXT, created_at TEXT,
    deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS honeypot_hits(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, path TEXT, ua TEXT);
"""

FORUM_SECTIONS = {1: "Databases & Leaks", 2: "Access Market", 3: "Logs & Combos", 4: "Fraud & Banking",
                  5: "General Chat"}


class Store:
    """One SQLite connection per thread: the web framework runs sync handlers in a thread pool, and sharing a
    single connection across threads causes 'API misuse' errors under concurrent requests."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.conn.executescript(SCHEMA)

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def reset(self) -> None:
        for table in ("members", "threads", "posts", "vendors", "listings", "victims", "pastes", "honeypot_hits"):
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.execute("DELETE FROM sqlite_sequence")

    def is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0] == 0

    # ----- members -----
    def add_member(self, name, persona, joined, pgp="", contact="", signature="", title="Member") -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO members(name, persona, joined, pgp, contact, signature, title) VALUES (?,?,?,?,?,?,?)",
            (name, persona, joined, pgp, contact, signature, title))
        if cur.lastrowid and cur.rowcount:
            return cur.lastrowid
        return self.conn.execute("SELECT uid FROM members WHERE name=?", (name,)).fetchone()[0]

    def member(self, uid: int):
        return self.conn.execute("SELECT * FROM members WHERE uid=?", (uid,)).fetchone()

    def member_by_name(self, name: str):
        return self.conn.execute("SELECT * FROM members WHERE name=?", (name,)).fetchone()

    def members(self):
        return self.conn.execute("SELECT * FROM members ORDER BY name").fetchall()

    def post_count(self, uid: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM posts p JOIN threads t ON t.tid=p.tid WHERE p.author_uid=? AND t.deleted=0",
            (uid,)).fetchone()[0]

    # ----- forum -----
    def create_thread(self, fid: int, title: str, author_uid: int, body: str, created_at: str) -> int:
        tid = self.conn.execute("INSERT INTO threads(fid, title, author_uid, created_at) VALUES (?,?,?,?)",
                                (fid, title, author_uid, created_at)).lastrowid
        self.conn.execute("INSERT INTO posts(tid, author_uid, body, created_at) VALUES (?,?,?,?)",
                          (tid, author_uid, body, created_at))
        return tid

    def add_reply(self, tid: int, author_uid: int, body: str, created_at: str) -> int:
        return self.conn.execute("INSERT INTO posts(tid, author_uid, body, created_at) VALUES (?,?,?,?)",
                                 (tid, author_uid, body, created_at)).lastrowid

    def delete_thread(self, tid: int) -> None:
        self.conn.execute("UPDATE threads SET deleted=1 WHERE tid=?", (tid,))

    def threads(self, fid: int | None = None, limit: int = 30):
        sql = ("SELECT t.*, m.name AS author, (SELECT COUNT(*) FROM posts p WHERE p.tid=t.tid) AS posts "
               "FROM threads t JOIN members m ON m.uid=t.author_uid WHERE t.deleted=0")
        args: list = []
        if fid is not None:
            sql += " AND t.fid=?"
            args.append(fid)
        sql += " ORDER BY t.created_at DESC LIMIT ?"
        args.append(limit)
        return self.conn.execute(sql, args).fetchall()

    def thread(self, tid: int):
        return self.conn.execute(
            "SELECT t.*, m.name AS author FROM threads t JOIN members m ON m.uid=t.author_uid WHERE t.tid=? AND t.deleted=0",
            (tid,)).fetchone()

    def thread_posts(self, tid: int):
        return self.conn.execute(
            "SELECT p.*, m.name AS author, m.uid AS uid, m.signature AS signature, m.title AS mtitle FROM posts p "
            "JOIN members m ON m.uid=p.author_uid WHERE p.tid=? ORDER BY p.created_at", (tid,)).fetchall()

    def section_counts(self) -> dict[int, int]:
        rows = self.conn.execute("SELECT fid, COUNT(*) FROM threads WHERE deleted=0 GROUP BY fid").fetchall()
        return {r[0]: r[1] for r in rows}

    # ----- market -----
    def add_vendor(self, name, persona, pgp, rating, sales, joined, wallet, about) -> None:
        self.conn.execute("INSERT OR REPLACE INTO vendors VALUES (?,?,?,?,?,?,?,?)",
                          (name, persona, pgp, rating, sales, joined, wallet, about))

    def vendor(self, name: str):
        return self.conn.execute("SELECT * FROM vendors WHERE name=?", (name,)).fetchone()

    def create_listing(self, vendor, title, category, price_usd, body, created_at) -> int:
        return self.conn.execute(
            "INSERT INTO listings(vendor, title, category, price_usd, body, created_at) VALUES (?,?,?,?,?,?)",
            (vendor, title, category, price_usd, body, created_at)).lastrowid

    def delete_listing(self, lid: int) -> None:
        self.conn.execute("UPDATE listings SET deleted=1 WHERE id=?", (lid,))

    def listings(self, vendor: str | None = None, limit: int = 40):
        if vendor:
            return self.conn.execute("SELECT * FROM listings WHERE deleted=0 AND vendor=? ORDER BY created_at DESC LIMIT ?",
                                     (vendor, limit)).fetchall()
        return self.conn.execute("SELECT * FROM listings WHERE deleted=0 ORDER BY created_at DESC LIMIT ?",
                                 (limit,)).fetchall()

    def listing(self, lid: int):
        return self.conn.execute("SELECT * FROM listings WHERE id=? AND deleted=0", (lid,)).fetchone()

    # ----- leak blog -----
    def create_victim(self, name, country, sector, website, deadline, status, data_size, description, created_at) -> int:
        return self.conn.execute(
            "INSERT INTO victims(name, country, sector, website, deadline, status, data_size, description, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (name, country, sector, website, deadline, status, data_size, description, created_at)).lastrowid

    def delete_victim(self, vid: int) -> None:
        self.conn.execute("UPDATE victims SET deleted=1 WHERE id=?", (vid,))

    def victims(self):
        return self.conn.execute("SELECT * FROM victims WHERE deleted=0 ORDER BY created_at DESC").fetchall()

    def victim(self, vid: int):
        return self.conn.execute("SELECT * FROM victims WHERE id=? AND deleted=0", (vid,)).fetchone()

    # ----- pastes -----
    def create_paste(self, title, author, body, created_at, pid: str | None = None) -> str:
        pid = pid or secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")
        self.conn.execute("INSERT INTO pastes(id, title, author, body, created_at) VALUES (?,?,?,?,?)",
                          (pid, title, author, body, created_at))
        return pid

    def delete_paste(self, pid: str) -> None:
        self.conn.execute("UPDATE pastes SET deleted=1 WHERE id=?", (pid,))

    def pastes(self, limit: int = 30):
        return self.conn.execute("SELECT * FROM pastes WHERE deleted=0 ORDER BY created_at DESC LIMIT ?",
                                 (limit,)).fetchall()

    def paste(self, pid: str):
        return self.conn.execute("SELECT * FROM pastes WHERE id=? AND deleted=0", (pid,)).fetchone()

    # ----- adversary mode helpers -----
    def created_between(self, since: str, until: str) -> list[tuple[str, str]]:
        """(kind, id) of every live post created in [since, until], across all four sites."""
        out: list[tuple[str, str]] = []
        for kind, table, key in (("thread", "threads", "tid"), ("listing", "listings", "id"),
                                 ("paste", "pastes", "id"), ("victim", "victims", "id")):
            for r in self.conn.execute(f"SELECT {key} FROM {table} WHERE deleted=0 AND created_at >= ? AND created_at <= ?",
                                       (since, until)):
                out.append((kind, str(r[0])))
        return out

    def delete_any(self, kind: str, key: str) -> None:
        {"thread": lambda: self.delete_thread(int(key)), "listing": lambda: self.delete_listing(int(key)),
         "paste": lambda: self.delete_paste(key), "victim": lambda: self.delete_victim(int(key))}[kind]()

    def publish_due_victims(self, now_iso_: str) -> list[int]:
        """Ransomware groups publish when the countdown ends: flip overdue countdowns to 'published'."""
        due = [r["id"] for r in self.conn.execute(
            "SELECT id FROM victims WHERE deleted=0 AND status='countdown' AND deadline <= ?", (now_iso_,))]
        for vid in due:
            self.conn.execute(
                "UPDATE victims SET status='published', description=description || ? WHERE id=?",
                ("\n\nDEADLINE PASSED. ALL DATA IS NOW PUBLISHED. Download links below (simulated, no files).", vid))
        return due

    def honeypot_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM honeypot_hits").fetchone()[0]

    # ----- honeypot -----
    def honeypot_hit(self, at: str, path: str, ua: str) -> None:
        self.conn.execute("INSERT INTO honeypot_hits(at, path, ua) VALUES (?,?,?)", (at, path, ua[:200]))

    def honeypot_hits(self):
        return self.conn.execute("SELECT * FROM honeypot_hits ORDER BY id DESC LIMIT 20").fetchall()
