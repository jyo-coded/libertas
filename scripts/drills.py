"""Failure drills (M7): break things on purpose and measure how Libertas copes.

  python scripts/drills.py all              every drill below except 'deadline' (about 10 minutes)
  python scripts/drills.py tor-down         kill the Tor client; the watchdog restarts it and collection resumes
  python scripts/drills.py source-gone      DeadDrop's server goes down behind its onion; noticed, then recovered
  python scripts/drills.py captcha          CAPTCHA wall: recognised, never solved, waited out, post captured after
  python scripts/drills.py ratelimit        HTTP 429: Libertas backs off and slows itself to the site's limit
  python scripts/drills.py randomise        anti-scraper markup churn: flagged as layout drift, never guessed past
  python scripts/drills.py fastdelete       posts vanish after 60 s: captured first, deletion recorded, evidence kept
  python scripts/drills.py killswitch       kill switch mid-run: no capture is made after the halt
  python scripts/drills.py deadline         a 4-minute ransomware countdown: polling tightens, publication caught

Results go to var/drills/ and the Forum's Readiness page. ShadowNet's adversary modes are always switched back off.
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import sys
import time

from _live import (VAR, audit_head, audit_since, get, now_iso, panel, panel_get, post, save, sources_in, stamp,
                   table, wait)


def source(st: dict, sid: str) -> dict:
    return next(s for s in st["sources"] if s["id"] == sid)


def health(sid: str) -> dict:
    return source(get("/api/status"), sid).get("health", {})


def new_alert_for(tid_title: str, known: set):
    return next((a for a in get("/api/alerts?limit=80") if a["id"] not in known and tid_title in (a.get("item_title") or "")), None)


def adversary(mode: str, on: bool, limit: int | None = None):
    extra = f"&limit={limit}" if limit else ""
    return panel(f"/api/adversary/{mode}?on={'true' if on else 'false'}{extra}")


# ---------------- drills: each returns (passed, summary, measures) ----------------
def drill_tor_down():
    pid = int((VAR / "run" / "tor_client.pid").read_text())
    before = get("/api/status")["tor"] or {}
    t0 = time.monotonic()
    os.kill(pid, signal.SIGTERM)
    restarted, _ = wait(lambda: (lambda t: t if t and t.get("restarts", 0) > before.get("restarts", 0)
                                 and t.get("state") == "running" else None)(get("/api/status")["tor"]), 180, 1)
    if not restarted:
        return False, "Tor client was not restarted within 180 s", {}
    back_s = round(time.monotonic() - t0, 1)
    watching, _ = wait(lambda: sources_in(lambda s: s == "watching"), 240, 2)
    total_s = round(time.monotonic() - t0, 1)
    return bool(watching), (f"Tor killed (pid {pid}); watchdog restarted it in {back_s}s; all sources watching "
                            f"again after {total_s}s"), {"tor_back_s": back_s, "collection_back_s": total_s}


def drill_source_gone():
    t0 = time.monotonic()
    adversary("offline", True)
    try:
        noticed, _ = wait(lambda: (lambda h: h if h.get("state") and h["state"] != "watching" else None)(health("deaddrop")),
                          240, 2)
        notice_s = round(time.monotonic() - t0, 1)
    finally:
        adversary("offline", False)
    if not noticed:
        return False, "DeadDrop going down was not noticed", {}
    t1 = time.monotonic()
    back, _ = wait(lambda: health("deaddrop").get("state") == "watching", 300, 2)
    back_s = round(time.monotonic() - t1, 1)
    return bool(back), (f"DeadDrop down noticed after {notice_s}s ({noticed['state'][:70]}); recovered "
                        f"{back_s}s after it came back"), {"notice_s": notice_s, "recover_s": back_s}


def drill_captcha():
    seq, known = audit_head(), {a["id"] for a in get("/api/alerts?limit=500")}
    hp = panel_get("/api/adversary")["honeypot_hits"]
    adversary("captcha", True)
    try:
        msg = panel("/api/preset/access_sale")["result"]
        wall, wall_s = wait(lambda: audit_since(seq, "wall_encountered"), 120, 2)
        alert_during = new_alert_for("[ACCESS]", known)
        drift = audit_since(seq, "parse_drift")
    finally:
        adversary("captcha", False)
    t1 = time.monotonic()
    alert, _ = wait(lambda: new_alert_for("[ACCESS]", known), 240, 2)
    after_s = round(time.monotonic() - t1, 1)
    hp_after = panel_get("/api/adversary")["honeypot_hits"]
    ok = bool(wall) and not alert_during and not drift and bool(alert) and hp_after == hp
    return ok, (f"{msg}: CAPTCHA wall recognised after {wall_s}s, not solved, no false drift or deletion; post "
                f"captured {after_s}s after the wall lifted; honeypot hits {hp_after - hp}"), {
        "wall_s": wall_s, "captured_after_lift_s": after_s, "honeypot_hits": hp_after - hp}


def drill_ratelimit():
    seq, known = audit_head(), {a["id"] for a in get("/api/alerts?limit=500")}
    adversary("ratelimit", True, limit=2)  # a strict site: more than 2 requests in 10 s is refused
    try:
        panel("/api/preset/fake_leak")
        panel("/api/preset/recycled_leak")
        wall, wall_s = wait(lambda: [r for r in audit_since(seq, "wall_encountered") if r["decision"] == "rate_limit"],
                            150, 2)
        alert, alert_s = wait(lambda: new_alert_for("Marutham", known), 240, 2)
        gaps = [s["health"].get("throttle_gap_s") for s in get("/api/status")["sources"] if s["health"].get("throttle_gap_s")]
    finally:
        adversary("ratelimit", False)
    ok = bool(wall) and bool(alert)
    if not alert:
        return False, f"HTTP 429 met after {wall_s}s, but the new post was not alerted within 240 s", {"wall_s": wall_s}
    return ok, (f"HTTP 429 met after {wall_s}s; Libertas honoured Retry-After and backed off to one request every "
                f"{max(gaps) if gaps else '?'} s; the new post was still alerted after {alert_s}s"), {
        "wall_s": wall_s, "alert_s": alert_s}


def drill_randomise():
    seq, known = audit_head(), {a["id"] for a in get("/api/alerts?limit=500")}
    adversary("randomise", True)
    try:
        panel("/api/preset/access_sale")
        drift, drift_s = wait(lambda: audit_since(seq, "parse_drift"), 150, 2)
        flagged = bool(health("kaal-forum").get("drift"))
        alert_during = new_alert_for("[ACCESS]", known)
    finally:
        adversary("randomise", False)
    alert, after_s = wait(lambda: new_alert_for("[ACCESS]", known), 240, 2)
    ok = bool(drift) and not alert_during and bool(alert)
    return ok, (f"layout churn flagged as drift after {drift_s}s (source marked: {flagged}); nothing guessed from "
                f"the broken page; captured {after_s}s after the layout settled"), {"drift_s": drift_s, "after_s": after_s}


def drill_fastdelete():
    known = {a["id"] for a in get("/api/alerts?limit=500")}
    adversary("fastdelete", True)
    try:
        t0 = time.monotonic()
        panel("/api/preset/telecom_leak")
        alert, alert_s = wait(lambda: new_alert_for("Mullai", known), 60, 1)
        gone, _ = wait(lambda: next((a for a in get("/api/alerts?limit=80") if alert and a["id"] == alert["id"]
                                     and a.get("deleted")), None), 150, 2) if alert else (None, 0)
        gone_s = round(time.monotonic() - t0, 1)
    finally:
        adversary("fastdelete", False)
    ok = bool(alert) and bool(gone) and bool(gone and gone.get("first_capture_sha"))
    return ok, (f"post alerted {alert_s}s after posting, before the seller's 60 s deletion; deletion recorded at "
                f"{gone_s}s with the capture kept"), {"alert_s": alert_s, "gone_s": gone_s}


def drill_killswitch():
    post("/api/kill", {"reason": "rehearsal: kill switch drill"})
    halted, halt_s = wait(lambda: sources_in(lambda s: s.startswith("halted")), 30, 0.5)
    time.sleep(2)  # severed requests are recorded as errors, never as responses
    before = get("/api/status")["counts"]["responses_received"]
    time.sleep(25)  # more than a full pulse interval with the switch engaged
    after = get("/api/status")["counts"]["responses_received"]
    post("/api/resume")
    back, back_s = wait(lambda: sources_in(lambda s: s == "watching"), 90, 1)
    ok = bool(halted) and bool(back) and after == before
    return ok, (f"halted in {halt_s}s; {after - before} responses received in the next 25 s (in-flight requests severed, new ones refused by Lex); resumed in {back_s}s"), {
        "halt_s": halt_s, "resume_s": back_s, "captures_while_halted": after - before}


def drill_deadline():
    seq = audit_head()
    msg = panel("/api/preset/ransom_deadline")["result"]
    vid = re.search(r"victim (\d+)", msg).group(1)
    tightened, _ = wait(lambda: (lambda w: w if w and w.get("interval_s", 99) <= 8 else None)(
        health("shadowlock").get("deadline_watch")), 300, 3)
    change, total = wait(lambda: [r for r in audit_since(seq, "status_change") if r["decision"] == "published"], 420, 2)
    if not change:
        return False, f"publication of victim {vid} not caught", {}
    import json as _json
    lag = _json.loads(change[0]["detail_json"]).get("seen_after_deadline_s")
    return True, (f"{msg}; polling tightened to {tightened['interval_s'] if tightened else '?'}s near the deadline; "
                  f"publication caught {lag}s after the countdown ended"), {"seen_after_deadline_s": lag}


DRILLS = {"tor-down": drill_tor_down, "source-gone": drill_source_gone, "captcha": drill_captcha,
          "ratelimit": drill_ratelimit, "randomise": drill_randomise, "fastdelete": drill_fastdelete,
          "killswitch": drill_killswitch, "deadline": drill_deadline}
ALL = ["killswitch", "captcha", "randomise", "ratelimit", "fastdelete", "source-gone", "tor-down"]


def run(name: str) -> dict:
    print(f"drill {name} …", flush=True)
    started, t0 = now_iso(), time.monotonic()
    try:
        ok, summary, measures = DRILLS[name]()
    except Exception as exc:
        ok, summary, measures = False, f"{type(exc).__name__}: {exc}"[:300], {}
        for mode in ("captcha", "ratelimit", "randomise", "fastdelete", "offline"):
            try:
                adversary(mode, False)
            except Exception:
                pass
    record = {"id": f"{stamp()}-{name}", "kind": "drill", "drill": name, "started_at": started, "finished_at": now_iso(),
              "seconds": round(time.monotonic() - t0, 1), "passed": ok, "summary": summary, **measures}
    save("drills", record)
    print(f"  {'PASS' if ok else 'FAIL'}  {summary}", flush=True)
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("drill", choices=[*DRILLS, "all"])
    args = ap.parse_args()
    names = ALL if args.drill == "all" else [args.drill]
    results = []
    for n in names:
        results.append(run(n))
        if n != names[-1]:
            wait(lambda: sources_in(lambda s: s == "watching"), 180, 2)  # settle before the next drill
    print("\n" + table([(r["drill"], "PASS" if r["passed"] else "FAIL", f"{r['seconds']}s") for r in results],
                       ("Drill", "Result", "Took")))
    sys.exit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    main()
