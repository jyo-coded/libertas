"""Libertas field test: measure Tor/onion behaviour against well-known legitimate onion services.

Experiments
  E1  fetch latency: first contact, same circuit (new stream), new circuit (cached descriptor), keep-alive
  E2  circuit isolation via SOCKS credentials (exit IPs on a clearnet check endpoint)
  E3  descriptor-only liveness probes (HSFETCH) for live onions and for random valid-but-nonexistent onions
Nothing here touches any criminal site, and nothing sends NEWNYM (would disturb the user's Tor Browser).
"""
import base64, binascii, hashlib, json, os, secrets, socket, statistics, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
SOCKS = os.environ.get("LIB_SOCKS", "127.0.0.1:19050")
CTRL = ("127.0.0.1", int(os.environ.get("LIB_CTRL", "19051")))
COOKIE = os.environ.get("LIB_COOKIE", os.path.join(_HERE, "tordata", "control_auth_cookie"))
UA = "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tor_field_results.json")

ONIONS = {
    "torproject": "2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion",
    "duckduckgo": "duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion",
    "bbc": "bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion",
    "nytimes": "nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljsciiyd.onion",
    "propublica": "p53lf57qovyuvwsc6xnrppyply3vtqm7l6pcobkmyqsiofyeznfu5uqd.onion",
    "securedrop": "sdolvtfhatvsysc6l34d65ymdwxcujausv7k5jk4cy5ttzhjoi6fzvyd.onion",
    "ahmia": "juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion",
}

# ---------- onion address helpers ----------
def onion_valid(addr):
    label = addr.replace(".onion", "")
    if len(label) != 56:
        return False
    try:
        raw = base64.b32decode(label.upper())
    except Exception:
        return False
    pub, chk, ver = raw[:32], raw[32:34], raw[34:]
    return ver == b"\x03" and hashlib.sha3_256(b".onion checksum" + pub + ver).digest()[:2] == chk

# minimal ed25519 base-point multiplication, to mint valid-but-unused v3 addresses
_q = 2**255 - 19
_d = (-121665 * pow(121666, _q - 2, _q)) % _q
_I = pow(2, (_q - 1) // 4, _q)
def _xrecover(y):
    xx = (y * y - 1) * pow(_d * y * y + 1, _q - 2, _q)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q:
        x = (x * _I) % _q
    return _q - x if x % 2 else x
_By = (4 * pow(5, _q - 2, _q)) % _q
_B = (_xrecover(_By), _By)
def _add(P, Q):
    x1, y1 = P; x2, y2 = Q
    t = _d * x1 * x2 * y1 * y2
    return ((x1 * y2 + x2 * y1) * pow(1 + t, _q - 2, _q) % _q,
            (y1 * y2 + x1 * x2) * pow(1 - t, _q - 2, _q) % _q)
def _mul(P, e):
    R = (0, 1)
    while e:
        if e & 1:
            R = _add(R, P)
        P = _add(P, P); e >>= 1
    return R
def random_onion():
    a = int.from_bytes(secrets.token_bytes(32), "little")
    a &= (1 << 254) - 8; a |= 1 << 254
    x, y = _mul(_B, a)
    pub = (y | ((x & 1) << 255)).to_bytes(32, "little")
    chk = hashlib.sha3_256(b".onion checksum" + pub + b"\x03").digest()[:2]
    return base64.b32encode(pub + chk + b"\x03").decode().lower() + ".onion"

# ---------- E1 fetch latency ----------
def curl(urls, user):
    cmd = ["curl", "-s", "--max-time", "120", "--proxy", f"socks5h://{user}:x@{SOCKS}", "-A", UA,
           "-w", "%{http_code} %{time_starttransfer} %{time_total} %{size_download} %{num_connects}\\n"]
    for u in urls:
        cmd += ["-o", os.devnull, u]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip().splitlines()
    res = []
    for line in out:
        p = line.split()
        if len(p) == 5:
            res.append({"code": p[0], "ttfb": float(p[1]), "total": float(p[2]), "bytes": int(p[3]), "new_conns": int(p[4])})
    return res

def probe(name, addr):
    url = f"http://{addr}/"
    u1, u2 = secrets.token_hex(6), secrets.token_hex(6)
    r = {"first_contact": curl([url], u1)}
    r["same_circuit_new_stream"] = curl([url], u1)
    r["new_circuit_cached_descriptor"] = curl([url], u2)
    r["keepalive_pair"] = curl([url, url], u2)
    return name, r

# ---------- E2 isolation ----------
def exit_ip(user):
    out = subprocess.run(["curl", "-s", "--max-time", "60", "--proxy", f"socks5h://{user}:x@{SOCKS}",
                          "https://check.torproject.org/api/ip"], capture_output=True, text=True).stdout
    try:
        return json.loads(out).get("IP")
    except Exception:
        return None

# ---------- E3 descriptor probes ----------
def ctrl_conn():
    s = socket.create_connection(CTRL, 10)
    f = s.makefile("rb")
    s.sendall(("AUTHENTICATE " + binascii.hexlify(open(COOKIE, "rb").read()).decode() + "\r\n").encode())
    assert f.readline().startswith(b"250"), "control auth failed"
    return s, f

def ctrl_cmd(s, f, c):
    s.sendall((c + "\r\n").encode())
    lines = []
    while True:
        l = f.readline().decode(errors="replace").rstrip("\r\n")
        lines.append(l)
        if l[:4] in ("250 ", "251 ", "550 ", "551 ", "552 ", "553 ", "510 ", "512 ", "513 ", "514 "):
            return lines

events, ev_lock = [], threading.Lock()
def event_listener(stop):
    s, f = ctrl_conn()
    s.sendall(b"SETEVENTS HS_DESC\r\n"); f.readline()
    s.settimeout(None)
    while not stop.is_set():  # blocking reads; daemon thread dies with the process
        l = f.readline()
        if not l:
            break
        l = l.decode(errors="replace").rstrip("\r\n")
        if l.startswith("650 HS_DESC"):
            with ev_lock:
                events.append((time.perf_counter(), l))

def desc_probe(s, f, onion, wait=60):
    label = onion.replace(".onion", "")
    t0 = time.perf_counter()
    resp = ctrl_cmd(s, f, "HSFETCH " + label)
    if not resp[-1].startswith("250"):
        return {"error": resp}
    while time.perf_counter() - t0 < wait:
        with ev_lock:
            mine = [(t, l) for t, l in events if t >= t0 and f" {label} " in l]
        req = [x for x in mine if " REQUESTED " in x[1]]
        rec = [x for x in mine if " RECEIVED " in x[1]]
        fail = [x for x in mine if " FAILED " in x[1]]
        if rec:
            return {"result": "RECEIVED", "seconds": round(rec[0][0] - t0, 2), "hsdirs_asked": len(req), "failed_before": len(fail)}
        if req and len(fail) >= len(req) and time.perf_counter() - t0 > 5:
            reasons = sorted({l.split("REASON=")[1].split()[0] for _, l in fail if "REASON=" in l})
            return {"result": "NOT_FOUND", "seconds": round(fail[-1][0] - t0, 2), "hsdirs_asked": len(req), "reasons": reasons}
        time.sleep(0.1)
    return {"result": "TIMEOUT", "seconds": wait}

def main():
    results = {"python": sys.version.split()[0]}
    t_boot = time.perf_counter()
    while True:  # wait for our own tor to start and bootstrap
        try:
            s, f = ctrl_conn()
            phase = ctrl_cmd(s, f, "GETINFO status/bootstrap-phase")[0]
            if "PROGRESS=100" in phase:
                break
            s.close()
        except (OSError, AssertionError):
            pass
        if time.perf_counter() - t_boot > 300:
            raise SystemExit("tor did not bootstrap within 300 s")
        time.sleep(2)
    results["bootstrap_seconds_seen_by_script"] = round(time.perf_counter() - t_boot, 1)
    print("bootstrapped", results["bootstrap_seconds_seen_by_script"], flush=True)
    results["tor_version"] = ctrl_cmd(s, f, "GETINFO version")[0]
    results["address_checks"] = {n: onion_valid(a) for n, a in ONIONS.items()}
    targets = {n: a for n, a in ONIONS.items() if onion_valid(a)}

    # E3 first (descriptor probes), so E1 "first contact" mostly uses descriptors fetched seconds earlier
    stop = threading.Event()
    th = threading.Thread(target=event_listener, args=(stop,), daemon=True); th.start()
    time.sleep(1)
    fakes = [random_onion() for _ in range(3)]
    results["fake_address_checks"] = [onion_valid(a) for a in fakes]
    desc = {}
    for n, a in list(targets.items()) + [(f"nonexistent_{i}", a) for i, a in enumerate(fakes)]:
        desc[n] = desc_probe(s, f, a)
        print("desc", n, desc[n], flush=True)
    results["E3_descriptor_probes"] = desc
    # outer-layer metadata of a fetched descriptor
    meta = {}
    for n, a in targets.items():
        r = ctrl_cmd(s, f, "GETINFO hs/client/desc/id/" + a.replace(".onion", ""))
        body = "\n".join(r)
        meta[n] = {k: next((l.split()[1] for l in r if l.startswith(k + " ")), None)
                   for k in ("descriptor-lifetime", "revision-counter")}
        meta[n]["bytes"] = len(body)
    results["descriptor_outer_meta"] = meta
    stop.set()
    if os.environ.get("LIB_ONLY_DESC"):
        print("meta", json.dumps(meta), flush=True)
        json.dump(results, open(OUT.replace(".json", "_desc.json"), "w"), indent=2)
        return

    # E1 fetch latency (sites probed concurrently, each site's steps sequential)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(targets)) as ex:
        fetch = dict(ex.map(lambda kv: probe(*kv), targets.items()))
    results["E1_wall_seconds_all_sites"] = round(time.perf_counter() - t0, 2)
    results["E1_fetch"] = fetch
    for n, r in fetch.items():
        print("fetch", n, json.dumps(r), flush=True)

    # E2 isolation
    a, b = secrets.token_hex(6), secrets.token_hex(6)
    results["E2_isolation"] = {"credA_1": exit_ip(a), "credA_2": exit_ip(a), "credB": exit_ip(b)}
    print("isolation", results["E2_isolation"], flush=True)

    def med(key, idx=0, field="total"):
        vals = [r[key][idx][field] for r in fetch.values() if len(r.get(key, [])) > idx and r[key][idx]["code"] != "000"]
        return (round(statistics.median(vals), 2), round(min(vals), 2), round(max(vals), 2), len(vals)) if vals else None
    results["summary_median_min_max_n"] = {
        "first_contact_total": med("first_contact"),
        "same_circuit_new_stream_total": med("same_circuit_new_stream"),
        "new_circuit_cached_descriptor_total": med("new_circuit_cached_descriptor"),
        "keepalive_second_request_total": med("keepalive_pair", 1),
    }
    print("summary", json.dumps(results["summary_median_min_max_n"]), flush=True)
    json.dump(results, open(OUT, "w"), indent=2)
    print("saved", OUT)

if __name__ == "__main__":
    main()
