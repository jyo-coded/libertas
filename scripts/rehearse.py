"""Demo rehearsal (blueprint section 20), run end to end against the live system with every beat timed.

  python scripts/rehearse.py                 one full run
  python scripts/rehearse.py --runs 3        the M7 acceptance test: three runs in a row, no intervention
  python scripts/rehearse.py --pace 8        pause 8 s between beats (for presenting, or recording the backup video)

Beats: preflight -> live incident (fast + deep lane) -> explainable verdict -> graph -> deletion -> evidence pack
(built, downloaded and verified offline) -> Lex boundary drill -> kill switch halt and resume -> audit chain.
Each run is saved under var/rehearsals/ and shown on the Forum's Readiness page.
"""
from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from _live import download, get, now_iso, panel, panel_form, post, save, sources_in, stamp, table, wait

TIMEOUT = 150


class Run:
    def __init__(self, n: int, pace: float):
        self.n, self.pace = n, pace
        self.beats: list[dict] = []
        self.ctx: dict = {}

    def beat(self, name: str, fn) -> bool:
        t0 = time.monotonic()
        try:
            ok, detail, measures = fn()
        except Exception as exc:  # a beat that crashes is a failed beat, never a crashed rehearsal
            ok, detail, measures = False, f"{type(exc).__name__}: {exc}"[:300], {}
        seconds = round(time.monotonic() - t0, 1)
        self.beats.append({"beat": name, "passed": ok, "seconds": seconds, "detail": detail, **measures})
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<26} {seconds:>6}s  {detail}", flush=True)
        if self.pace:
            time.sleep(self.pace)
        return ok

    # ---------- beats ----------
    def preflight(self):
        st = get("/api/status")
        if st["kill_engaged"]:
            post("/api/resume")
        ready, waited = wait(lambda: sources_in(lambda s: s == "watching"), 120, 2)
        if not ready:
            return False, "not every source is watching", {}
        hb = (ready.get("heartbeat") or {})
        audit_ok = ready["audit"]["ok"]
        self.ctx["alert_ids"] = {a["id"] for a in get("/api/alerts?limit=500")}
        median = hb.get("median_lag_s")
        detail = (f"{len(ready['sources'])}/{len(ready['sources'])} sources watching; heartbeat {hb.get('state', 'n/a')}"
                  + (f" (median {median} s)" if median else "")
                  + f"; audit chain {'intact' if audit_ok else 'BROKEN'}")
        return audit_ok, detail, {"sources_wait_s": waited, "heartbeat_median_s": hb.get("median_lag_s")}

    def live_incident(self):
        t0 = time.monotonic()
        msg = panel("/api/preset/telecom_leak")["result"]
        tid = int(re.search(r"thread (\d+)", msg).group(1))
        self.ctx["tid"] = tid

        def fresh():
            return next((a for a in get("/api/alerts?limit=60")
                         if a["id"] not in self.ctx["alert_ids"] and a.get("status") == "new"
                         and "Mullai" in (a.get("item_title") or "")), None)

        alert, _ = wait(fresh, TIMEOUT)
        if not alert:
            return False, f"no alert within {TIMEOUT}s for forum thread {tid}", {}
        fast_s = round(time.monotonic() - t0, 1)
        self.ctx["alert"] = alert

        def deep():
            a = next((x for x in get("/api/alerts?limit=100") if x["id"] == alert["id"]), None)
            return a if a and a.get("deep") and not a.get("provisional") else None

        confirmed, _ = wait(deep, 60, 0.5)
        if not confirmed:
            return False, "fast alert, but the deep lane never ruled", {"fast_s": fast_s}
        deep_s = round(time.monotonic() - t0, 1)
        d = confirmed["deep"]
        self.ctx["item_id"] = confirmed["item_id"]
        return True, (f"MSG-{confirmed['item_id']:04d} {confirmed['severity']} logged {fast_s}s after posting "
                      f"(capture lag {confirmed['detection_lag_s']}s); deep verdict {d['authenticity']} at {deep_s}s"), {
            "alert_s": fast_s, "deep_s": deep_s, "detection_lag_s": confirmed["detection_lag_s"],
            "severity": confirmed["severity"], "verdict": d["authenticity"]}

    def explain(self):
        d = get(f"/api/items/{self.ctx['item_id']}/deep")
        actor = ((d.get("attribution") or {}).get("actor") or {}).get("label")
        exposure = [e["entity"] for m in (d.get("money") or {}).values() for e in m.get("exposure", [])]
        ok = bool(actor) and bool(exposure) and d["authenticity"]["verdict"] == "likely_genuine"
        return ok, (f"authenticity {d['authenticity']['verdict']}; actor {actor or 'none'}; "
                    f"money to {exposure[0].split(' (')[0] if exposure else 'nobody'}"), {"actor": actor}

    def graph(self):
        g = get(f"/api/graph?focus=item:{self.ctx['item_id']}&depth=2")
        types = {n["type"] for n in g["nodes"]}
        ok = {"actor", "cluster"} <= types or {"actor", "wallet"} <= types
        return ok, f"{len(g['nodes'])} nodes, {len(g['edges'])} links; actor and wallet cluster present: {ok}", {}

    def deletion(self):
        t0 = time.monotonic()
        panel_form(f"/forum/delete/{self.ctx['tid']}")
        aid = self.ctx["alert"]["id"]
        gone, _ = wait(lambda: next((a for a in get("/api/alerts?limit=100") if a["id"] == aid and a.get("deleted")),
                                    None), TIMEOUT)
        if not gone:
            return False, f"deletion not detected within {TIMEOUT}s", {}
        s = round(time.monotonic() - t0, 1)
        return True, f"seller's deletion caught after {s}s; capture {gone['first_capture_sha'][:12]}… kept", {"deletion_s": s}

    def evidence(self):
        t0 = time.monotonic()
        pack = post(f"/api/items/{self.ctx['item_id']}/evidence")
        build_s = round(time.monotonic() - t0, 1)
        blob = download(pack["download"])
        with tempfile.TemporaryDirectory() as tmp:
            zipfile.ZipFile(io.BytesIO(blob)).extractall(tmp)
            verify = next(Path(tmp).rglob("verify.py"))
            # our own generated pack; -I keeps the verifier isolated from this project's modules
            r = subprocess.run([sys.executable, "-I", str(verify), str(verify.parent)], capture_output=True,
                               text=True, timeout=120)
        ok = r.returncode in (0, 3)
        summary = (r.stdout.strip().splitlines() or ["(no output)"])[-1][:120]
        return ok, f"{pack['pack_id']} built in {build_s}s, verified offline: {summary}", {
            "pack_build_s": build_s, "pack_id": pack["pack_id"], "verify_exit": r.returncode}

    def lex(self):
        r = post("/api/lex/drill")
        return r["passed"] and r["audit"]["ok"], f"{r['refused']}/{r['total']} forbidden attempts refused and audited", {}

    def kill_switch(self):
        t0 = time.monotonic()
        post("/api/kill", {"reason": "rehearsal: kill switch drill"})
        halted, _ = wait(lambda: sources_in(lambda s: s.startswith("halted")), 30, 0.5)
        halt_s = round(time.monotonic() - t0, 1)
        t1 = time.monotonic()
        post("/api/resume")
        back, _ = wait(lambda: sources_in(lambda s: s == "watching"), 90, 1)
        resume_s = round(time.monotonic() - t1, 1)
        ok = bool(halted) and bool(back)
        return ok, f"all collection halted in {halt_s}s; watching again {resume_s}s after release", {
            "halt_s": halt_s, "resume_s": resume_s}

    def audit(self):
        v = get("/api/audit/verify")
        return v["ok"], f"hash chain intact across {v['entries_checked']} entries", {}


def rehearse(n: int, pace: float) -> dict:
    run = Run(n, pace)
    started = now_iso()
    print(f"\nRehearsal run {n}  ({started})", flush=True)
    steps = [("Preflight", run.preflight), ("Live incident", run.live_incident), ("Explainable verdict", run.explain),
             ("Graph", run.graph), ("Deletion", run.deletion), ("Evidence pack", run.evidence),
             ("Lex boundary", run.lex), ("Kill switch", run.kill_switch), ("Audit chain", run.audit)]
    for name, fn in steps:
        if not run.beat(name, fn) and name in ("Preflight", "Live incident"):
            break  # later beats need the incident
    record = {"id": f"{stamp()}-run{n}", "kind": "rehearsal", "started_at": started, "finished_at": now_iso(),
              "passed": len(run.beats) == len(steps) and all(b["passed"] for b in run.beats), "beats": run.beats}
    save("rehearsals", record)
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--pace", type=float, default=0.0, help="seconds to pause after each beat")
    args = ap.parse_args()
    results = [rehearse(i + 1, args.pace) for i in range(args.runs)]
    beats = [b["beat"] for b in results[0]["beats"]]
    rows = [(b, *(next((f"{x['seconds']}s {'ok' if x['passed'] else 'FAIL'}" for x in r["beats"] if x["beat"] == b), "-")
                  for r in results)) for b in beats]
    print("\n" + table(rows, ("Beat", *(f"Run {i + 1}" for i in range(len(results))))))
    passed = sum(r["passed"] for r in results)
    print(f"\n{passed}/{len(results)} runs passed without intervention")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
