"""Lex: the lawful boundary, enforced on every request (blueprint §17, §11.14).

Phase 0 rules for collectors:
  * kill switch halts everything
  * GET only (no forms, logins or posting)
  * onion only: clearnet egress is refused, and every address must pass the v3 checksum
  * development mode: only allowlisted onions (ShadowNet + benchmark sites)
  * abuse blocklist (MD5 of the onion domain, Ahmia format)
  * no file downloads: archives, executables, documents, images and media are metadata only
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from ..common.onion import is_valid_v3, onion_label
from .audit import AuditLog

BLOCKED_EXTENSIONS = frozenset({
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".zst", ".cab",
    ".exe", ".msi", ".dll", ".scr", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse", ".wsf", ".hta",
    ".jar", ".apk", ".dmg", ".iso", ".img", ".bin", ".elf", ".sh", ".py", ".lnk",
    ".pdf", ".doc", ".docx", ".docm", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".rtf", ".odt", ".ods",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tif", ".tiff", ".heic",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".wav", ".ogg", ".flac",
    ".torrent", ".sql", ".csv", ".db", ".sqlite", ".bak", ".dump", ".mdb", ".accdb",
})


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


class Lex:
    def __init__(self, audit: AuditLog, *, mode: str, kill_file: Path, allowlist: set[str] | None = None,
                 blocklist_file: Path | None = None):
        self.audit = audit
        self.mode = mode
        self.kill_file = Path(kill_file)
        self.allowlist: set[str] = {a.lower() for a in (allowlist or set())}
        self.blocklist_md5: set[str] = set()
        if blocklist_file and Path(blocklist_file).exists():
            self.blocklist_md5 = {
                line.strip().lower() for line in Path(blocklist_file).read_text().splitlines() if len(line.strip()) == 32}

    # ----- kill switch -----
    def kill_engaged(self) -> bool:
        return self.kill_file.exists()

    def engage_kill(self, actor: str, reason: str) -> None:
        self.kill_file.parent.mkdir(parents=True, exist_ok=True)
        self.kill_file.write_text(reason or "kill switch engaged")
        self.audit.append(actor, "kill_switch", "collection", "engaged", {"reason": reason})

    def release_kill(self, actor: str) -> None:
        if self.kill_file.exists():
            self.kill_file.unlink()
        self.audit.append(actor, "kill_switch", "collection", "released", {})

    # ----- allowlist -----
    def allow(self, label: str, *, actor: str = "system", why: str = "") -> None:
        label = label.lower()
        if label not in self.allowlist:
            self.allowlist.add(label)
            self.audit.append(actor, "allowlist_add", label, "allowed", {"why": why})

    # ----- the check every collector request must pass -----
    def check_fetch(self, method: str, url: str, *, source_id: str = "") -> Decision:
        reason = self._evaluate(method, url)
        if reason:
            self.audit.append("lex", "fetch", url[:300], "deny", {"reason": reason, "source": source_id, "method": method})
            return Decision(False, reason)
        return Decision(True, "allowed")

    def _evaluate(self, method: str, url: str) -> str:
        if self.kill_engaged():
            return "kill switch engaged"
        if method.upper() != "GET":
            return "only GET is permitted for collectors"
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            return "malformed URL"
        if parts.scheme not in ("http", "https"):
            return "scheme not permitted"
        if parts.username or parts.password:
            return "credentials in URL are not permitted"
        host = (parts.hostname or "").lower()
        if not host.endswith(".onion"):
            return "clearnet egress refused for collectors"
        label = onion_label(host)
        if not label or not is_valid_v3(label):
            return "invalid onion address (v3 checksum failed)"
        if port not in (None, 80, 443):
            return "non-web port refused"
        if hashlib.md5(f"{label}.onion".encode()).hexdigest() in self.blocklist_md5:
            return "onion is on the abuse blocklist"
        if self.mode == "development" and label not in self.allowlist:
            return "onion not on the development allowlist"
        ext = PurePosixPath(unquote(parts.path or "/")).suffix.lower()
        if ext in BLOCKED_EXTENSIONS:
            return f"file download refused ({ext}); recorded as metadata only"
        return ""
