"""Evidence pack builder (blueprint #33): one call produces a self-verifying ZIP.

Contents: original captures (bit-exact), masked readable text, Merkle inclusion proofs, RFC 3161 tokens, a signed
manifest, chain of custody, a PDF report, a BSA §63 certificate draft, legal-request drafts and a standalone
verifier. The export itself is recorded in the hash-chained audit log.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import secrets
import shutil
import socket
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from .. import __version__
from ..common.timeutil import now, to_ist
from ..config import Settings
from ..interpres.india import mask_pii
from ..janus.quarantine import Quarantine
from ..janus.sanitize import decode, parse_html, parse_json
from ..lex.audit import AuditLog
from ..tabularium.merkle import capture_leaf
from ..tabularium.service import Tabularium
from ..tabularium.signing import Signer
from . import legal
from .report import build_report_pdf

FORMAT = "libertas-evidence-pack/1"
VERIFY_SOURCE = Path(__file__).with_name("verify_pack.py")
PACK_ID_RE = re.compile(r"^LIB-EVD-\d{8}-\d{5}-[0-9A-F]{4}$")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:40] or "entity"


class EvidencePackBuilder:
    def __init__(self, conn: sqlite3.Connection, audit: AuditLog, quarantine: Quarantine, tabularium: Tabularium,
                 signer: Signer, settings: Settings, out_dir: Path):
        self.conn, self.audit, self.quarantine, self.tabularium = conn, audit, quarantine, tabularium
        self.signer, self.settings, self.out_dir = signer, settings, Path(out_dir)

    def _captures(self, url: str) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
        rows = self.conn.execute("SELECT * FROM captures WHERE url=? AND sha256 IS NOT NULL ORDER BY id", (url,)).fetchall()
        selected, last = [], None
        for r in rows:  # first capture of every distinct version, plus the final check
            if r["sha256"] != last:
                selected.append(r)
                last = r["sha256"]
        if rows and selected[-1]["id"] != rows[-1]["id"]:
            selected.append(rows[-1])
        return selected, rows

    @staticmethod
    def _readable(raw: bytes, content_type: str, url: str) -> str:
        if content_type in ("text/html", "application/xhtml+xml"):
            return parse_html(raw, url, content_type).text
        if content_type == "application/json":
            try:
                return json.dumps(parse_json(raw), indent=2, ensure_ascii=False)
            except ValueError:
                pass
        return decode(raw, content_type)

    def _custody(self, item_id: int, url: str, batch_ids: list[int], all_caps: list[sqlite3.Row]) -> list[dict]:
        targets = [f"item:{item_id}"] + [f"batch:{b}" for b in batch_ids]
        rows = self.conn.execute(
            f"SELECT ts, actor, action, target, decision, detail_json FROM audit_log WHERE target IN "
            f"({','.join('?' * len(targets))}) OR (action='fetch' AND target=?) ORDER BY seq", (*targets, url[:300])).fetchall()
        out = []
        for r in rows:
            detail = json.loads(r["detail_json"] or "{}")
            parts = [f"{k}: {v}" for k, v in detail.items() if not isinstance(v, (dict, list)) and len(str(v)) <= 70][:4]
            out.append({"time_utc": r["ts"], "actor": r["actor"], "action": r["action"], "target": r["target"],
                        "detail": r["decision"] + (" · " + "; ".join(parts) if parts else "")})
        for c in all_caps:
            role = json.loads(c["headers_json"] or "{}").get("role", "")
            out.append({"time_utc": c["fetched_at"], "actor": "speculatores", "action": f"capture ({role})",
                        "target": f"capture:{c['id']}", "sha256": c["sha256"], "status": c["status"],
                        "detail": f"HTTP {c['status']}, {c['bytes']} bytes, sha256 {c['sha256'][:16]}…, isolated circuit "
                                  f"{c['isolation_id']}"})
        out.sort(key=lambda e: e["time_utc"])
        for e in out:
            e["time_ist"] = to_ist(e["time_utc"])
        return out

    @staticmethod
    def _condense(custody: list[dict]) -> list[dict]:
        """For the PDF only: collapse runs of identical re-checks (same content, same status) into one row."""
        view: list[dict] = []
        for e in custody:
            prev = view[-1] if view else None
            if (prev and e["action"] == "capture (revisit)" and prev["action"].startswith("capture (revisit)")
                    and e.get("sha256") == prev.get("sha256") and e.get("status") == prev.get("status")):
                prev["count"] += 1
                prev["action"] = f"capture (revisit) ×{prev['count']}"
                prev["time_ist"] = f"{prev['first_ist']} → {e['time_ist']}"
                prev["target"] = f"{prev['first_target']} …"
                prev["detail"] = f"content unchanged · {prev['base_detail']}"
                continue
            view.append({**e, "count": 1, "first_ist": e["time_ist"], "first_target": e["target"], "base_detail": e["detail"]})
        return view

    async def build(self, item_id: int, requested_by: str = "operator") -> dict:
        conn = self.conn
        item = conn.execute("SELECT i.*, s.name AS source_name, s.onion AS onion, s.simulated AS simulated FROM items i "
                            "JOIN sources s ON s.id=i.source_id WHERE i.id=?", (item_id,)).fetchone()
        if not item:
            raise KeyError(f"item {item_id} not found")
        await self.tabularium.ensure_sealed()
        caps, all_caps = self._captures(item["url"])
        if not caps:
            raise ValueError(f"item {item_id} has no stored captures")
        alert = conn.execute("SELECT * FROM alerts WHERE item_id=?", (item_id,)).fetchone()
        assessment = conn.execute("SELECT * FROM assessments WHERE item_id=?", (item_id,)).fetchone()
        deep_row = conn.execute("SELECT * FROM deep_assessments WHERE item_id=?", (item_id,)).fetchone()
        alert_fj = json.loads(alert["factors_json"] or "{}") if alert else {}
        cats = json.loads(assessment["categories_json"] or "[]") if assessment else []
        orgs = [o["org"] for o in json.loads(assessment["orgs_json"] or "[]")] if assessment else []
        sectors = sorted({o["sector"] for o in json.loads(assessment["orgs_json"] or "[]")}) if assessment else []
        attribution = json.loads(deep_row["attribution_json"] or "null") if deep_row else None
        money = json.loads(deep_row["money_json"] or "{}") if deep_row else {}
        ts = now()
        pack_id = f"LIB-EVD-{ts:%Y%m%d}-{item_id:05d}-{secrets.token_hex(2).upper()}"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="pack-", dir=self.out_dir))
        try:
            for sub in ("captures/raw", "captures/text", "timestamps", "certificate", "legal"):
                (work / sub).mkdir(parents=True, exist_ok=True)
            cap_entries, batch_ids, first_text = [], [], ""
            for c in caps:
                raw = self.quarantine.get(c["sha256"])
                raw_rel, text_rel = f"captures/raw/{c['sha256']}.capture", f"captures/text/{c['sha256']}.txt"
                (work / raw_rel).write_bytes(raw)
                text = mask_pii(self._readable(raw, c["content_type"], c["url"]))
                (work / text_rel).write_text(text, encoding="utf-8")
                first_text = first_text or text
                proof = self.tabularium.proof("capture", c["id"])
                if not proof:
                    raise RuntimeError(f"capture {c['id']} is not sealed")
                batch_ids.append(proof["batch_id"])
                cap_entries.append({
                    "capture_id": c["id"], "sha256": c["sha256"], "md5": _md5(raw), "bytes": len(raw), "url": c["url"],
                    "fetched_at": c["fetched_at"], "fetched_ist": to_ist(c["fetched_at"]), "status": c["status"],
                    "content_type": c["content_type"], "source_id": c["source_id"], "isolation_id": c["isolation_id"],
                    "role": json.loads(c["headers_json"] or "{}").get("role", ""), "file": raw_rel, "text_file": text_rel,
                    "raw_file": raw_rel, "leaf_data": capture_leaf(c),
                    "merkle": {"batch_id": proof["batch_id"], "leaf_index": proof["leaf_index"], "path": proof["path"]}})
            batches = {}
            for bid in dict.fromkeys(batch_ids):
                b = conn.execute("SELECT * FROM merkle_batches WHERE id=?", (bid,)).fetchone()
                info = json.loads(b["tsa_info_json"] or "{}")
                entry = {"root": b["root"], "created_at": b["created_at"], "size": b["size"], "audit_seq": b["audit_seq"],
                         "audit_head": b["audit_head"], "internal_signature": b["signature"], "status": b["status"],
                         "tsa_url": b["tsa_url"], "tsa": info,
                         "tsa_time_ist": to_ist(b["tsa_gen_time"]) if b["tsa_gen_time"] else
                         ("pending" if b["status"] == "tsa_pending" else "not requested"),
                         "tsa_name": (info.get("tsa_subject") or "—")[:80]}
                if b["tsr"]:
                    entry["tsr_file"] = f"timestamps/batch-{bid}.tsr"
                    (work / entry["tsr_file"]).write_bytes(b["tsr"])
                batches[str(bid)] = entry
            for c in cap_entries:
                c["batch_id"] = c["merkle"]["batch_id"]
                c["tsa_time_ist"] = batches[str(c["batch_id"])]["tsa_time_ist"]

            last_present = max((c["fetched_at"] for c in all_caps if c["status"] == 200), default=item["last_seen"])
            existence = {"claimed_posted_at": item["posted_at"], "first_seen": item["first_seen"],
                         "last_seen_present": last_present, "first_seen_absent": item["deleted_at"]}
            exposures = []
            for wallet, mv in money.items():
                for e in mv.get("exposure", []):
                    exposures.append({"wallet": wallet, "cluster": mv["cluster_id"], "entity": e["entity"], "btc": e["btc"],
                                      "deposits": e["deposits"], "txids": e["txids"],
                                      "basis": [f"{ev['heuristic']} (confidence {ev['confidence']}) in tx {ev['txid'][:16]}…"
                                                for ev in mv.get("evidence", [])][:6]
                                      + [mv.get("note", "")]})
            ctx = {
                "pack_id": pack_id, "generated_utc": ts.isoformat(timespec="seconds"), "generated_ist": to_ist(ts.isoformat()),
                "generated_date_ist": to_ist(ts.isoformat())[:10], "unit": self.settings.unit_name, "operator": requested_by,
                "host": socket.gethostname(), "os": f"{platform.system()} {platform.release()}",
                "system": f"Libertas {__version__}", "simulation": bool(item["simulated"]),
                "item": {"id": item_id, "title": item["title"] or "", "author": item["author"] or "", "kind": item["kind"]},
                "source": {"name": item["source_name"], "onion": item["onion"], "url": item["url"]},
                "existence": {**existence, "claimed_posted_ist": to_ist(item["posted_at"]),
                              "first_seen_ist": to_ist(item["first_seen"]), "last_seen_ist": to_ist(last_present),
                              "first_seen_absent_ist": to_ist(item["deleted_at"])},
                "category": cats[0]["label"] if cats else "—", "orgs": orgs, "sectors": sectors,
                "severity": alert["severity"] if alert else "—", "score": alert["score"] if alert else "—",
                "fast_severity": (alert_fj.get("fast") or {}).get("severity") or (alert["severity"] if alert else "—"),
                "deep": alert_fj.get("deep"),
                "indicators": [dict(r) for r in conn.execute(
                    "SELECT kind, display, valid, sensitive FROM indicators WHERE item_id=? ORDER BY sensitive, kind",
                    (item_id,))],
                "attribution_links": (attribution or {}).get("links", []), "exposures": exposures,
                "captures": cap_entries, "batches": batches, "text": first_text,
                "custody": self._custody(item_id, item["url"], [int(b) for b in batches], all_caps),
                "audit": self.audit.verify(), "signing_fingerprint": self.signer.fingerprint,
            }

            legal_files: list[tuple[str, str]] = []

            def write(rel: str, text: str, desc: str) -> None:
                (work / rel).write_text(text, encoding="utf-8")
                legal_files.append((rel, desc))

            ctx["section63_text"] = legal.section63_certificate(ctx)
            write("certificate/BSA_section63_certificate_DRAFT.txt", ctx["section63_text"],
                  "certificate under Section 63(4)(c) BSA 2023: Part A pre-filled, Part B worksheet for the expert")
            if orgs:
                write("legal/victim_notification_DRAFT.txt", legal.victim_notification(ctx),
                      f"confidential notification to {', '.join(orgs)}")
            write("legal/CERT-In_incident_report_DRAFT.txt", legal.certin_report(ctx), "incident report for CERT-In")
            for entity in {e["entity"] for e in exposures}:
                ex = [e for e in exposures if e["entity"] == entity]
                merged = {"entity": entity, "btc": round(sum(e["btc"] for e in ex), 8),
                          "deposits": sorted({d for e in ex for d in e["deposits"]}),
                          "txids": sorted({t for e in ex for t in e["txids"]}), "basis": ex[0]["basis"]}
                write(f"legal/BNSS94_notice_{_slug(entity)}_DRAFT.txt", legal.bnss94_vasp_notice(ctx, merged),
                      f"notice under Section 94 BNSS 2023 to {entity} for the deposit accounts")
            handles = sorted({i["display"].lstrip("@") for i in ctx["indicators"] if i["kind"] == "telegram"})
            if handles:
                write("legal/telegram_request_DRAFT.txt", legal.telegram_request(ctx, handles),
                      "preservation and disclosure request to Telegram")
            ctx["legal_files"] = legal_files
            ctx["custody_view"] = self._condense(ctx["custody"])
            ctx["verify_text"] = self._readme(ctx)
            (work / "README.txt").write_text(ctx["verify_text"], encoding="utf-8")
            build_report_pdf(work / "report.pdf", ctx)
            shutil.copyfile(VERIFY_SOURCE, work / "verify.py")
            (work / "signing_key.pub").write_text(self.signer.public_pem, encoding="utf-8")

            files = []
            for p in sorted(work.rglob("*")):
                if p.is_file():
                    b = p.read_bytes()
                    files.append({"path": p.relative_to(work).as_posix(), "sha256": _sha256(b), "md5": _md5(b), "bytes": len(b)})
            manifest = {
                "format": FORMAT, "pack_id": pack_id, "generated_at_utc": ctx["generated_utc"],
                "generated_at_ist": ctx["generated_ist"], "simulation": ctx["simulation"],
                "generated_by": {"system": ctx["system"], "host": ctx["host"], "os": ctx["os"], "unit": ctx["unit"],
                                 "operator": requested_by},
                "subject": {**ctx["item"], "source": ctx["source"], "category": ctx["category"], "organisations": orgs},
                "existence_window": existence,
                "alert": {"id": alert["id"], "severity": alert["severity"], "score": alert["score"],
                          "fast": alert_fj.get("fast"), "deep": alert_fj.get("deep")} if alert else None,
                "facts": {"indicators": ctx["indicators"],
                          "versions": [dict(r) for r in conn.execute(
                              "SELECT seen_at, content_hash, capture_sha FROM item_versions WHERE item_id=? ORDER BY id",
                              (item_id,))]},
                "leads": {"disclaimer": "Inferred by automated analysis (T2/T3). Investigative leads, not proof.",
                          "authenticity": json.loads(deep_row["authenticity_json"]) if deep_row else None,
                          "attribution": attribution, "money": money,
                          "correlation": json.loads(deep_row["correlation_json"]) if deep_row else None},
                "captures": [{k: v for k, v in c.items() if k not in ("fetched_ist", "raw_file", "tsa_time_ist", "batch_id")}
                             for c in cap_entries],
                "batches": {k: {kk: vv for kk, vv in v.items() if kk not in ("tsa_time_ist", "tsa_name")}
                            for k, v in batches.items()},
                "custody": ctx["custody"], "audit_chain": ctx["audit"],
                "signing_key": {"algorithm": "Ed25519", "fingerprint_sha256": self.signer.fingerprint,
                                "public_key_file": "signing_key.pub"},
                "hash_algorithms": ["SHA-256", "MD5"], "files": files,
            }
            mbytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
            (work / "manifest.json").write_bytes(mbytes)
            (work / "manifest.sig").write_text(self.signer.sign(mbytes), encoding="utf-8")
            manifest_sha = _sha256(mbytes)
            (work / "RECEIPT.txt").write_text(
                f"Libertas evidence pack {pack_id}\nmanifest.json SHA-256: {manifest_sha}\nGenerated: {ctx['generated_ist']}\n"
                f"Evidence signing key (Ed25519): {self.signer.fingerprint}\n", encoding="utf-8")
            zip_path = self.out_dir / f"{pack_id}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for p in sorted(work.rglob("*")):
                    if p.is_file():
                        z.write(p, f"{pack_id}/{p.relative_to(work).as_posix()}")
        finally:
            shutil.rmtree(work, ignore_errors=True)
        zip_sha = _sha256(zip_path.read_bytes())
        summary = {"pack_id": pack_id, "item_id": item_id, "captures": len(cap_entries), "batches": len(batches),
                   "timestamped": sum(1 for b in batches.values() if b.get("tsr_file")), "files": len(files) + 3,
                   "manifest_sha256": manifest_sha, "zip_sha256": zip_sha, "zip_bytes": zip_path.stat().st_size,
                   "legal_drafts": [n for n, _ in legal_files]}
        conn.execute("INSERT INTO evidence_packs(id, created_at, item_id, alert_id, created_by, manifest_sha256, zip_sha256, "
                     "path, summary_json) VALUES (?,?,?,?,?,?,?,?,?)",
                     (pack_id, ctx["generated_utc"], item_id, alert["id"] if alert else None, requested_by, manifest_sha,
                      zip_sha, str(zip_path), json.dumps(summary)))
        self.audit.append(requested_by, "evidence_export", f"item:{item_id}", "created",
                          {"pack_id": pack_id, "manifest_sha256": manifest_sha, "zip_sha256": zip_sha})
        return {**summary, "path": str(zip_path)}

    def _readme(self, ctx: dict) -> str:
        tsa = self.settings.tsa_url if self.settings.tsa_enabled else "(external timestamps disabled)"
        return f"""LIBERTAS EVIDENCE PACK {ctx['pack_id']}
{'SIMULATION: produced from ShadowNet training data; everything in it is fictional.' if ctx['simulation'] else ''}
Contents
  report.pdf                 human-readable evidence report (personal data masked)
  manifest.json / .sig       machine-readable record of everything in this pack, signed with Ed25519
  signing_key.pub            public half of the Libertas evidence signing key
  captures/raw/*.capture     ORIGINAL bytes exactly as received over Tor. Hostile web content: never open in a browser.
  captures/text/*.txt        readable text extracted from each capture (personal data masked)
  timestamps/batch-N.tsr     RFC 3161 timestamp tokens ({tsa}) on the Merkle batch roots
  certificate/               draft certificate under Section 63(4)(c), BSA 2023
  legal/                     drafts for officer review: notices, notifications, reports
  verify.py                  independent verifier (Python 3; optional: pip install cryptography asn1crypto)
  RECEIPT.txt                SHA-256 of manifest.json

How to verify
  1. In this folder:  python verify.py
  2. Any single file without Python:
       Windows:        certutil -hashfile captures\\raw\\<file> SHA256
       Linux/macOS:    sha256sum captures/raw/<file>
     and compare with manifest.json and section 5 of report.pdf.
  3. Timestamps with OpenSSL (batch roots are listed in manifest.json):
       openssl ts -reply -in timestamps/batch-N.tsr -text
       openssl ts -verify -digest <batch root hex> -in timestamps/batch-N.tsr -CAfile <TSA CA certificate>
"""
