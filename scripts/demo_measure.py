"""Live demo measurement: publish a ShadowNet preset, then time how long Libertas takes to raise the alert through
Tor. Optionally delete the post and time deletion detection.

  python scripts/demo_measure.py                      # telecom_leak preset, then delete it
  python scripts/demo_measure.py --preset access_sale --no-delete
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

PANEL = "http://127.0.0.1:8600"
API = "http://127.0.0.1:8700"


def post(url: str) -> None:
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as exc:  # the panel answers with a 303 redirect
        if exc.code not in (302, 303):
            raise


def get(path: str):
    return json.load(urllib.request.urlopen(API + path, timeout=20))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="telecom_leak")
    ap.add_argument("--no-delete", action="store_true")
    ap.add_argument("--timeout", type=float, default=180)
    args = ap.parse_args()

    before = {a["id"] for a in get("/api/alerts?limit=500")}
    t0 = time.time()
    post(f"{PANEL}/preset/{urllib.parse.quote(args.preset)}")
    print(f"published preset '{args.preset}' at {time.strftime('%H:%M:%S')}")
    alert = None
    while time.time() - t0 < args.timeout:
        fresh = [a for a in get("/api/alerts?limit=50") if a["id"] not in before and a.get("status") == "new"]
        if fresh:
            alert = fresh[0]
            break
        time.sleep(1)
    if not alert:
        print("NO ALERT within timeout")
        return
    wall = round(time.time() - t0, 1)
    print(f"ALERT after {wall}s (wall clock, incl. 1s polling): {alert['severity']} {alert['score']}, {alert['title']}")
    print(f"  detection lag (posted -> first seen through Tor): {alert['detection_lag_s']} s")
    for reason in alert.get("reasons", [])[:5]:
        print("  -", reason)
    print(f"  evidence: sha256 {alert['first_capture_sha']}")
    while time.time() - t0 < args.timeout:
        a = next((x for x in get("/api/alerts?limit=100") if x["id"] == alert["id"]), None)
        if a and a.get("deep"):
            d = a["deep"]
            print(f"DEEP LANE confirmed after {round(time.time() - t0, 1)}s from publication "
                  f"({d.get('latency_s')}s after the fast alert): {d['severity']} {d['score']} "
                  f"(fast lane said {a.get('fast', {}).get('severity')} {a.get('fast', {}).get('score')})")
            for reason in d.get("reasons", [])[:7]:
                print("  *", reason[:240])
            break
        time.sleep(1)
    else:
        print("deep lane did not confirm within timeout")
    if args.no_delete:
        return
    t1 = time.time()
    post(f"{PANEL}/preset/delete_latest")
    print(f"deleted the post at {time.strftime('%H:%M:%S')}; waiting for Libertas to notice")
    while time.time() - t1 < args.timeout:
        a = next((x for x in get("/api/alerts?limit=100") if x["id"] == alert["id"]), None)
        if a and a.get("deleted"):
            print(f"DELETION detected after {round(time.time() - t1, 1)}s; evidence kept: {a['first_capture_sha']}")
            return
        time.sleep(1)
    print("deletion NOT detected within timeout")


if __name__ == "__main__":
    main()
