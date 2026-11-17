"""Decrypt v3 onion descriptors of legitimate onions (fetched via our own tor's control port) and report
what an outside observer can learn without touching site content: intro point count, PoW defence params, flags."""
import binascii, os, socket, sys, json
from stem.descriptor.hidden_service import HiddenServiceDescriptorV3

HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE = os.path.join(HERE, "tordata", "control_auth_cookie")
TARGETS = {
    "torproject": "2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid",
    "duckduckgo": "duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad",
    "bbc": "bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd",
    "securedrop": "sdolvtfhatvsysc6l34d65ymdwxcujausv7k5jk4cy5ttzhjoi6fzvyd",
    "ahmia": "juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd",
}

s = socket.create_connection(("127.0.0.1", 19051), 30)
f = s.makefile("rb")
s.sendall(("AUTHENTICATE " + binascii.hexlify(open(COOKIE, "rb").read()).decode() + "\r\n").encode())
assert f.readline().startswith(b"250")

def getinfo_desc(addr):
    s.sendall(f"GETINFO hs/client/desc/id/{addr}\r\n".encode())
    first = f.readline().decode(errors="replace").rstrip("\r\n")
    if not first.startswith("250+"):
        raise ValueError(f"no cached descriptor: {first}")
    body = []
    while True:  # data block ends with a lone "." line, then "250 OK"
        l = f.readline().decode(errors="replace").rstrip("\r\n")
        if l == ".":
            f.readline()
            break
        body.append(l[1:] if l.startswith("..") else l)
    return "\n".join(body) + "\n"

out = {}
for name, addr in TARGETS.items():
    try:
        raw = getinfo_desc(addr)
        desc = HiddenServiceDescriptorV3(raw.encode())
        inner = desc.decrypt(addr + ".onion")
        inner_text = str(inner)
        pow_lines = [l for l in inner_text.splitlines() if l.startswith("pow-params")]
        flags = [l for l in inner_text.splitlines() if l.split(" ")[0] in ("single-onion-service", "intro-auth-required", "flow-control", "create2-formats")]
        out[name] = {
            "intro_points": len(inner.introduction_points),
            "pow_params": [" ".join(p.split()[:2] + ["<seed>"] + p.split()[3:]) for p in pow_lines],
            "flags": flags,
        }
    except Exception as e:
        out[name] = {"error": f"{type(e).__name__}: {e}"}
    print(name, json.dumps(out[name]), flush=True)
