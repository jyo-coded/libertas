"""M5 'done when': one call produces a verifiable evidence pack, and tampering is detected."""
import asyncio
import importlib.util
import io
import json
import re
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import httpx

from libertas.codex import EvidencePackBuilder
from libertas.config import Settings
from libertas.interpres.india import verhoeff_valid
from libertas.speculatores.adapters import ItemRef
from libertas.tabularium import Signer, Tabularium
from shadownet.world import preset_delete_latest, preset_telecom_leak

from .harness import Env

FIXTURES = Path(__file__).parent / "fixtures"
OFFLINE = Settings(tsa_enabled=False)


def _run_verifier(pack: Path) -> tuple[int, str]:
    spec = importlib.util.spec_from_file_location("pack_verify", pack / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mod.main(["verify.py", str(pack)])
    return code, buf.getvalue()


def test_evidence_pack_end_to_end(tmp_path):
    env = Env(tmp_path)
    signer = Signer(tmp_path / "key.pem")
    tab = Tabularium(env.conn, env.audit, signer, OFFLINE)
    builder = EvidencePackBuilder(env.conn, env.audit, env.pipe.quarantine, tab, signer, OFFLINE, tmp_path / "evidence")

    async def scenario():
        await env.sweep()
        preset_telecom_leak(env.store)
        await env.sweep()
        item = env.item("n1ghtcr4wl")
        await env.deep.process([item["id"]])
        preset_delete_latest(env.store)  # the seller deletes the post; Libertas re-checks and records the 404
        src = next(s for s in env.sources if s.id == item["source_id"])
        await env.fetch_detail(src, ItemRef(item["item_key"], item["url"], item["kind"]))
        return item, await builder.build(item["id"], requested_by="test-officer")

    item, res = asyncio.run(scenario())
    assert res["captures"] >= 2 and res["batches"] >= 1
    out = tmp_path / "unzipped"
    with zipfile.ZipFile(res["path"]) as z:
        z.extractall(out)
    pack = out / res["pack_id"]

    code, report = _run_verifier(pack)
    assert "0 failed" in report and code == 3, report  # 3 = everything passed, external timestamps skipped (offline)
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["existence_window"]["first_seen_absent"], "deletion must be part of the existence window"
    assert manifest["leads"]["attribution"]["actor"]["label"] == "cybo_kaal"
    assert (pack / "report.pdf").read_bytes().startswith(b"%PDF")
    cert = (pack / "certificate/BSA_section63_certificate_DRAFT.txt").read_text(encoding="utf-8")
    assert manifest["captures"][0]["sha256"] in cert and "PART B" in cert
    assert any(p.name.startswith("BNSS94_notice_SimEx") for p in (pack / "legal").iterdir())
    assert (pack / "legal/victim_notification_DRAFT.txt").exists()

    # personal data: masked in readable text, intact in the original capture
    first = manifest["captures"][0]
    raw = (pack / first["file"]).read_bytes().decode("utf-8", "replace")
    text = (pack / first["text_file"]).read_text(encoding="utf-8")
    full = [g for g in re.findall(r"\b(\d{4}) (\d{4}) (\d{4})\b", raw) if verhoeff_valid("".join(g))]
    assert full, "the original must keep the exact bytes"
    assert not any(" ".join(g) in text for g in full) and "XXXX XXXX" in text

    # tamper with ONE byte of an original capture: verification must fail
    target = pack / first["file"]
    data = bytearray(target.read_bytes())
    data[len(data) // 2] ^= 0x01
    target.write_bytes(bytes(data))
    code, report = _run_verifier(pack)
    assert code == 1 and "VERIFICATION FAILED" in report

    exports = env.conn.execute("SELECT detail_json FROM audit_log WHERE action='evidence_export'").fetchall()
    assert len(exports) == 1 and json.loads(exports[0][0])["pack_id"] == res["pack_id"]
    assert env.audit.verify()["ok"]


def test_tsa_answer_for_the_wrong_digest_is_rejected(tmp_path):
    env = Env(tmp_path)
    signer = Signer(tmp_path / "key.pem")
    fixture = (FIXTURES / "freetsa_probe.tsr").read_bytes()
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=fixture,
                                                             headers={"content-type": "application/timestamp-reply"}))
    tab = Tabularium(env.conn, env.audit, signer, Settings(tsa_enabled=True), transport=transport, log=lambda m: None)

    async def scenario():
        await env.sweep()
        await tab.ensure_sealed()

    asyncio.run(scenario())
    batch = env.conn.execute("SELECT status, error FROM merkle_batches ORDER BY id DESC LIMIT 1").fetchone()
    assert batch["status"] == "tsa_pending" and "does not cover" in batch["error"]
