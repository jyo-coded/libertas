"""ShadowNet's fictional world and content generator. EVERYTHING here is invented.

Organisations use the reserved .example TLD. Aadhaar-format numbers start with 1 and mobiles with 5, ranges
never issued to real people. Wallets are Bitcoin *regtest* addresses (bcrt1...), which can't exist on mainnet.

Four hidden personas operate several aliases each, with distinct writing habits, so Libertas's attribution
engine (Stilus, M4) can be scored against a known ground truth.
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass
from datetime import datetime, timedelta

from libertas.common.onion import random_v3_label
from libertas.common.timeutil import now
from libertas.interpres.cryptoaddr import B58, encode_segwit
from libertas.interpres.india import verhoeff_digit

from .store import Store

ORGS = {
    "kurinji": {"name": "Kurinji Health Trust", "short": "Kurinji Health", "sector": "healthcare",
                "domain": "kurinjihealth.example", "city": "Madurai"},
    "mullai": {"name": "Mullai Telecom", "short": "Mullai Telecom", "sector": "telecom",
               "domain": "mullaitelecom.example", "city": "Chennai"},
    "marutham": {"name": "Marutham Co-operative Bank", "short": "Marutham Bank", "sector": "banking",
                 "domain": "maruthambank.example", "city": "Thanjavur"},
    "neithal": {"name": "Neithal University", "short": "Neithal Univ", "sector": "education",
                "domain": "neithal-univ.example", "city": "Nagapattinam"},
    "palai": {"name": "Palai Water Board", "short": "Palai Water", "sector": "government",
              "domain": "palaiwater.example", "city": "Ramanathapuram"},
    "nilavu": {"name": "Nilavu Logistics", "short": "Nilavu Logistics", "sector": "corporate",
               "domain": "nilavulogistics.example", "city": "Coimbatore"},
}
SECTOR_WORD = {"healthcare": "patient", "telecom": "subscriber", "banking": "customer", "education": "student",
               "government": "consumer", "corporate": "employee"}
FIRST = ["Arun", "Priya", "Karthik", "Divya", "Senthil", "Lakshmi", "Vignesh", "Meena", "Suresh", "Anitha",
         "Prakash", "Kavya", "Murugan", "Revathi", "Dinesh", "Saranya"]
INITIALS = list("KMRSVPTAN")
CITIES = ["Chennai", "Madurai", "Coimbatore", "Tiruchirappalli", "Salem", "Tirunelveli", "Vellore", "Erode",
          "Thanjavur", "Thoothukudi"]


# ---------------- synthetic identifiers ----------------
def sim_aadhaar(r: random.Random, valid: bool = True) -> str:
    base = "1" + "".join(r.choice(string.digits) for _ in range(10))
    check = verhoeff_digit(base)
    if not valid:
        check = str((int(check) + r.randint(1, 9)) % 10)
    d = base + check
    return f"{d[:4]} {d[4:8]} {d[8:]}"


def sim_mobile(r: random.Random) -> str:
    return "+91 5" + "".join(r.choice(string.digits) for _ in range(4)) + " " + "".join(
        r.choice(string.digits) for _ in range(5))


def sim_btc(r: random.Random) -> str:
    return encode_segwit("bcrt", 0, bytes(r.getrandbits(8) for _ in range(20)))


def sim_xmr(r: random.Random) -> str:
    return "4" + r.choice("0123456789AB") + "".join(r.choice(B58) for _ in range(93))


def pgp_fp(r: random.Random) -> str:
    hexs = "".join(r.choice("0123456789ABCDEF") for _ in range(40))
    return " ".join(hexs[i:i + 4] for i in range(0, 40, 4))


def tox_id(r: random.Random) -> str:
    return "".join(r.choice("0123456789ABCDEF") for _ in range(76))


def session_id(r: random.Random) -> str:
    return "05" + "".join(r.choice("0123456789abcdef") for _ in range(64))


def sample_rows(r: random.Random, org: dict, n: int = 4, valid: bool = True,
                fields=("name", "mobile", "aadhaar", "city")) -> str:
    rows = [" | ".join(fields)]
    for _ in range(n):
        vals = {"name": f"{r.choice(FIRST)} {r.choice(INITIALS)}.", "mobile": sim_mobile(r),
                "aadhaar": sim_aadhaar(r, valid), "city": org["city"] if r.random() < 0.6 else r.choice(CITIES),
                "email": f"{r.choice(FIRST).lower()}{r.randint(10, 99)}@{org['domain']}",
                "customer_id": f"{org['short'][:3].upper()}{r.randint(100000, 999999)}"}
        rows.append(" | ".join(vals[f] for f in fields))
    return "\n".join(rows)


def fmt_indian(n: int) -> str:
    if n >= 10_000_000:
        return f"{n / 10_000_000:.1f}".rstrip("0").rstrip(".") + " crore"
    if n >= 100_000:
        return f"{n / 100_000:.0f} lakh"
    return f"{n:,}"


def fmt_plain(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# ---------------- personas ----------------
@dataclass
class Persona:
    key: str
    style: str
    pgp: str
    wallets: list[str]
    contact: str


def _build_personas() -> dict[str, Persona]:
    r = random.Random(20261117)
    return {p.key: p for p in (
        Persona("P1", "kaal", pgp_fp(r), [sim_btc(r), sim_btc(r)], f"tox {tox_id(r)}"),
        Persona("P2", "formal", pgp_fp(r), [sim_btc(r)], f"Session ID {session_id(r)}"),
        Persona("P3", "volk", pgp_fp(r), [sim_btc(r), sim_xmr(r)], "jabber volk_access@xmpp.shadownet.example"),
        Persona("P4", "hinglish", pgp_fp(r), [sim_btc(r)], "tg @logsbhai_sim"),
    )}


PERSONAS = _build_personas()

# (name, persona, title, signature, joined_days_ago, shows_pgp)
FORUM_MEMBERS = [
    ("cybo_kaal", "P1", "Verified Seller", "~k | quality data only", 400, True),
    ("n1ghtcr4wl", "P1", "Newbie", "", 3, False),
    ("data_baniya", "P2", "Seller", "Trusted since 2024. Kindly use escrow.", 520, True),
    ("volk_access", "P3", "Access Broker", "no test. no free.", 610, True),
    ("bhai_logs", "P4", "Member", "logs ka baap", 210, True),
    ("chai_coder", None, "Member", "", 300, False),
    ("silent_owl", None, "Member", "", 150, False),
    ("escrow_bot", None, "Staff", "Kaal Forum escrow service", 900, False),
]
VENDORS = [("KaalDataHouse", "P1", 4.8, 312), ("TrustedSeller_IN", "P2", 4.5, 188), ("VolkAccess", "P3", 4.9, 97),
           ("LogsKing", "P4", 4.3, 541)]


# ---------------- text generators (one voice per persona) ----------------
def db_sale(r, persona: Persona, org: dict, records: int, price: int, *, valid=True, wallet=None):
    sample = sample_rows(r, org, valid=valid)
    wallet = wallet or persona.wallets[0]
    word = SECTOR_WORD[org["sector"]]
    if persona.style == "kaal":
        return (f"[FRESH] {org['name']} — {fmt_indian(records)} {word} db",
                f"fresh {org['sector']} db straight from {org['short'].lower()} servers bro\n"
                f"{fmt_indian(records)} rows. fields: name, mobile, aadhaar, city\n"
                f"pulled {r.randint(2, 9)} days ago, not resold, not public anywhere\n\n"
                f"sample:\n{sample}\n\nprice ${price} btc only -> {wallet}\n"
                f"no timewasters. dm on {persona.contact}\n~k")
    if persona.style == "formal":
        return (f"{org['name']} Customer Database ({fmt_indian(records)} Records) - Genuine",
                "Dear Sir/Madam,\n\nKindly note we are having the "
                f"{org['name']} {word} database of {fmt_indian(records)} records ({org['sector']} sector). "
                "Data is genuine and recently extracted. Fields: Name, Mobile, Aadhaar, City.\n\n"
                f"Price: Rs. {price * 83:,} only or equivalent USDT (TRC20). Kindly do the needful and revert back "
                f"on {persona.contact}.\n\nSample for verification:\n{sample}\n\nThanks and regards.")
    if persona.style == "volk":
        return (f"{org['name']} database {fmt_plain(records)} lines",
                f"Have database of {org['name']}, India. {fmt_plain(records)} lines, fields name/phone/aadhaar/city.\n"
                f"Price is {price}$, negotiable only for regular clients. Escrow only!!!\n\nSample:\n{sample}\n\n"
                f"{persona.contact}\nBTC for direct deal: {wallet}")
    return (f"{org['short']} ka fresh data — {fmt_indian(records)}",
            f"bhai ekdum fresh data {org['short']} ka 🔥🔥\n{fmt_indian(records)} records, aadhaar + mobile sab hai\n"
            f"sample dekho:\n{sample}\n\nprice sirf ${price} 💸 jaldi dm karo 😎 {persona.contact}\nwallet: {wallet}")


def access_sale(r, persona: Persona, sector: str, revenue_m: int, employees: int, access: str, privileges: str,
                price_k: int):
    return (f"[ACCESS] India | {sector.title()} | Rev {revenue_m}M$ | {access}",
            f"Selling access to Indian company.\nSector: {sector}\nRevenue: {revenue_m}M$\nEmployees: {employees}\n"
            f"Access: {access}\nPrivileges: {privileges}\n"
            f"AV: {r.choice(['Defender', 'Sophos', 'CrowdStrike', 'Trend Micro'])}\n"
            f"Price: {price_k}k$ via forum escrow only. No test, no free, no reseller.\n{persona.contact}")


def logs_sale(r, persona: Persona, thousands: int, price: int, org_a: dict, org_b: dict):
    return (f"India logs {thousands}k fresh 🔥 banking + upi apps",
            f"bhai {thousands}k fresh India logs 🔥 stealer se nikale, last week ke\n"
            f"{org_a['domain']} aur {org_b['domain']} ke employee logins bhi hai 👀\n"
            "banking, upi apps, email sab milega 💸\n"
            f"price sirf ${price} per 1k logs, bulk me discount 😎\n{persona.contact}\nwallet: {persona.wallets[0]}")


def fraud_infra(r, persona: Persona):
    if persona.style == "formal":
        return ("Corporate Current Accounts (All Banks) - Kindly Contact",
                "Dear Sir,\n\nWe are having corporate current accounts with net banking, UPI and cheque book. "
                "KYC is fully done. Kindly note accounts are for rent on monthly basis.\n"
                f"Rate: Rs. {r.randint(25, 60)},000 per account per month. Kindly revert on {persona.contact}.")
    return ("current accounts ready — KYC done, UPI active 🏦",
            "bhai current + savings accounts ready hai 🏦\nKYC done, net banking + UPI chalu\n"
            f"per account ₹{r.randint(8, 20)},000, monthly rent bhi possible\n"
            f"test handle: sim.mule.{r.randint(1, 9999):04d}@ybl\ndm {persona.contact}")


NOISE = [
    ("new mirror for sona bazaar?", "anyone got the new mirror for sona bazaar? old one is down since morning"),
    ("vouch KaalDataHouse", "vouch for KaalDataHouse, got the db within 10 mins. legit"),
    ("escrow slow today?", "escrow taking 6+ hours today, anyone else?"),
    ("tool request: combo cleaner", "looking for a combo cleaner that handles indian mobile formats"),
    ("forum rules reminder", "No free leaks in Databases section. Use escrow. Scammers get banned."),
]
REPLIES = ["vouch", "pm sent", "price negotiable?", "bump", "legit seller", "sample looks real", "any discount bro?"]


# ---------------- seeding ----------------
def seed(store: Store) -> dict:
    r = random.Random(42)
    t0 = now()

    def ago(days: float, hours: float = 0) -> str:
        return (t0 - timedelta(days=days, hours=hours, minutes=r.randint(0, 59))).isoformat(timespec="seconds")

    store.reset()
    uid = {}
    for name, pk, title, sig, joined_days, show_pgp in FORUM_MEMBERS:
        p = PERSONAS.get(pk) if pk else None
        uid[name] = store.add_member(name, pk or "", ago(joined_days), p.pgp if (p and show_pgp) else "",
                                     p.contact if (p and show_pgp) else "", sig, title)
    noise_members = ["chai_coder", "silent_owl"]
    P = PERSONAS

    def thread(days, fid, author, title_body, replies=True):
        title, body = title_body
        created = ago(days)
        tid = store.create_thread(fid, title, uid[author], body, created)
        if replies:
            for k in range(r.randint(0, 2)):
                reply_at = (datetime.fromisoformat(created) + timedelta(hours=1 + k * 3)).isoformat(timespec="seconds")
                store.add_reply(tid, uid[r.choice(noise_members)], r.choice(REPLIES), reply_at)
        return tid

    O = ORGS
    thread(26, 1, "cybo_kaal", db_sale(r, P["P1"], O["kurinji"], 3_400_000, 1800))
    thread(18, 1, "cybo_kaal", db_sale(r, P["P1"], O["neithal"], 640_000, 600))
    thread(9, 1, "cybo_kaal", db_sale(r, P["P1"], O["nilavu"], 210_000, 350))
    thread(4, 1, "cybo_kaal", db_sale(r, P["P1"], O["palai"], 1_150_000, 900))
    thread(22, 1, "data_baniya", db_sale(r, P["P2"], O["marutham"], 2_600_000, 2500))
    thread(15, 1, "data_baniya", db_sale(r, P["P2"], O["kurinji"], 900_000, 700))
    thread(7, 1, "data_baniya", db_sale(r, P["P2"], O["palai"], 480_000, 400))
    thread(20, 1, "volk_access", db_sale(r, P["P3"], O["nilavu"], 750_000, 1200))
    thread(28, 2, "volk_access", access_sale(r, P["P3"], "telecom", 900, 6000, "Citrix + VPN", "domain user", 12))
    thread(16, 2, "volk_access", access_sale(r, P["P3"], "banking", 300, 1800, "RDP", "local admin", 8))
    thread(10, 2, "volk_access", access_sale(r, P["P3"], "government", 40, 900, "VPN (Fortinet)", "domain admin", 15))
    thread(3, 2, "volk_access", access_sale(r, P["P3"], "education", 25, 1200, "webshell + VPN", "domain user", 4))
    thread(25, 3, "bhai_logs", logs_sale(r, P["P4"], 18, 40, O["mullai"], O["marutham"]))
    thread(14, 3, "bhai_logs", logs_sale(r, P["P4"], 32, 35, O["kurinji"], O["palai"]))
    thread(5, 3, "bhai_logs", logs_sale(r, P["P4"], 9, 55, O["neithal"], O["nilavu"]))
    thread(19, 4, "bhai_logs", fraud_infra(r, P["P4"]))
    thread(11, 4, "data_baniya", fraud_infra(r, P["P2"]))
    thread(2, 4, "bhai_logs", fraud_infra(r, P["P4"]))
    for i, (title, body) in enumerate(NOISE):
        thread(27 - i * 5, 5, ["chai_coder", "silent_owl", "chai_coder", "silent_owl", "escrow_bot"][i], (title, body),
               replies=False)

    # ----- market -----
    for name, pk, rating, sales in VENDORS:
        p = P[pk]
        store.add_vendor(name, pk, p.pgp, rating, sales, ago(300 + sales // 3), p.wallets[0],
                         {"P1": "quality indian data. fast delivery. ~k", "P2": "Genuine data only. Kindly use escrow.",
                          "P3": "Corporate access. Verified before listing.", "P4": "logs ka baap 🔥 daily fresh"}[pk])
    for days, vendor, maker, cat, price in [
        (24, "KaalDataHouse", lambda: db_sale(r, P["P1"], O["kurinji"], 3_400_000, 1800), "Databases", 1800),
        (12, "KaalDataHouse", lambda: db_sale(r, P["P1"], O["neithal"], 640_000, 600), "Databases", 600),
        (21, "TrustedSeller_IN", lambda: db_sale(r, P["P2"], O["marutham"], 2_600_000, 2500), "Databases", 2500),
        (6, "TrustedSeller_IN", lambda: fraud_infra(r, P["P2"]), "Bank Accounts", 600),
        (17, "VolkAccess", lambda: access_sale(r, P["P3"], "telecom", 900, 6000, "Citrix + VPN", "domain user", 12),
         "Access", 12000),
        (8, "LogsKing", lambda: logs_sale(r, P["P4"], 32, 35, O["kurinji"], O["palai"]), "Logs", 35),
        (2, "LogsKing", lambda: logs_sale(r, P["P4"], 9, 55, O["neithal"], O["nilavu"]), "Logs", 55),
    ]:
        title, body = maker()
        store.create_listing(vendor, title, cat, price, body, ago(days))

    # ----- ShadowLock leak blog -----
    def victim(name, country, sector, website, status, size, days_ago, deadline_days, what):
        deadline = (t0 + timedelta(days=deadline_days)).isoformat(timespec="seconds")
        desc = (f"{name} ({country}) — {sector}. We have exfiltrated {size} of internal data: {what}. "
                + ("Data is now published below." if status == "published" else
                   f"If {name} does not contact us before the deadline, everything will be published."))
        store.create_victim(name, country, sector, website, deadline, status, size, desc, ago(days_ago))

    victim(O["kurinji"]["name"], "IN", "healthcare", O["kurinji"]["domain"], "published", "412 GB", 29, -14,
           "patient records, lab reports, HR files")
    victim("Harborview Dental Group", "US", "healthcare", "harborviewdental.example", "published", "88 GB", 23, -9,
           "patient files, billing")
    victim("Ostrava Freight s.r.o.", "CZ", "logistics", "ostravafreight.example", "published", "130 GB", 17, -3,
           "contracts, finance")
    victim(O["nilavu"]["name"], "IN", "corporate", O["nilavu"]["domain"], "countdown", "57 GB", 6, 5,
           "customer database, invoices, scanned IDs")
    victim("Lindqvist Maskin AB", "SE", "manufacturing", "lindqvistmaskin.example", "countdown", "210 GB", 2, 9,
           "engineering drawings, payroll")

    # ----- DeadDrop pastes -----
    store.create_paste("proof sample", "anon_k", sample_rows(r, O["neithal"], n=6), ago(17))
    combo = "\n".join(f"{r.choice(FIRST).lower()}{r.randint(10, 999)}@{r.choice(list(ORGS.values()))['domain']}:"
                      f"{''.join(r.choice(string.ascii_letters + string.digits) for _ in range(10))}" for _ in range(12))
    store.create_paste("india combo sample 2k", "logs_bhai", combo, ago(13))
    mirrors = "\n".join(f"http://{random_v3_label()}.onion" for _ in range(3))
    store.create_paste("sona bazaar mirrors (signed)", "Anonymous",
                       f"-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\nOfficial Sona Bazaar mirrors:\n{mirrors}\n"
                       "-----BEGIN PGP SIGNATURE-----\n(simulated signature)\n-----END PGP SIGNATURE-----", ago(10))
    store.create_paste("hello", "Anonymous", "testing deaddrop. hello world.", ago(8))
    return {"threads": len(store.threads(limit=1000)), "listings": len(store.listings(limit=1000)),
            "victims": len(store.victims()), "pastes": len(store.pastes(limit=1000))}


# ---------------- live demo presets (triggered from the local control panel) ----------------
def preset_telecom_leak(store: Store) -> str:
    r = random.Random()
    p, org = PERSONAS["P1"], ORGS["mullai"]
    sample = sample_rows(r, org, n=5)
    author = store.member_by_name("n1ghtcr4wl")["uid"]
    body = (f"mullai telecom subscriber db, fresh. 1.2 crore rows bro\n"
            f"fields: name, mobile, aadhaar, city, plan, activation date\n"
            f"pulled 3 days ago straight from their crm, not resold, not public anywhere\n\n"
            f"sample:\n{sample}\n\nprice $4500 btc only -> {p.wallets[1]}\n"
            f"no timewasters. dm on {p.contact}")
    tid = store.create_thread(1, "Mullai Telecom — 1.2 crore subscriber db, fresh", author, body,
                              now().isoformat(timespec="seconds"))
    return f"forum thread {tid} posted by n1ghtcr4wl"


def preset_fake_leak(store: Store) -> str:
    r = random.Random()
    title, body = db_sale(r, PERSONAS["P2"], ORGS["marutham"], 5_000_000, 3000, valid=False)
    tid = store.create_thread(1, title, store.member_by_name("data_baniya")["uid"], body,
                              now().isoformat(timespec="seconds"))
    return f"forum thread {tid} (sample with invalid checksums)"


def preset_access_sale(store: Store) -> str:
    r = random.Random()
    title, body = access_sale(r, PERSONAS["P3"], "healthcare", 120, 2400, "VPN + RDP", "domain admin", 9)
    tid = store.create_thread(2, title, store.member_by_name("volk_access")["uid"], body,
                              now().isoformat(timespec="seconds"))
    return f"forum thread {tid} (initial access sale)"


def preset_ransom_victim(store: Store) -> str:
    t0 = now()
    org = ORGS["neithal"]
    vid = store.create_victim(org["name"], "IN", "education", org["domain"],
                              (t0 + timedelta(hours=72)).isoformat(timespec="seconds"), "countdown", "96 GB",
                              f"{org['name']} (IN) — education. We have exfiltrated 96 GB of internal data: student "
                              f"records, exam results, staff payroll. If {org['name']} does not contact us before "
                              "the deadline, everything will be published.", t0.isoformat(timespec="seconds"))
    return f"ShadowLock victim {vid} with a 72h countdown"


def preset_ransom_deadline(store: Store) -> str:
    """A countdown that ends four minutes from now. ShadowNet publishes the data the moment it expires."""
    t0 = now()
    org = ORGS["kurinji"]
    vid = store.create_victim(org["name"], "IN", "healthcare", org["domain"],
                              (t0 + timedelta(minutes=4)).isoformat(timespec="seconds"), "countdown", "212 GB",
                              f"{org['name']} (IN) — healthcare. 212 GB of patient records, insurance claims and lab "
                              "reports. Final warning: publication when the timer ends.", t0.isoformat(timespec="seconds"))
    return f"ShadowLock victim {vid} with a 4-minute countdown"


def _sample_lines(body: str) -> list[str]:
    return [line for line in body.splitlines() if line.count("|") >= 2]


def _latest_thread_body(store: Store, author: str, contains: str = "") -> str | None:
    m = store.member_by_name(author)
    if not m:
        return None
    row = store.conn.execute(
        "SELECT p.body FROM posts p JOIN threads t ON t.tid=p.tid WHERE p.author_uid=? AND p.body LIKE ? "
        "ORDER BY p.created_at DESC LIMIT 1", (m["uid"], f"%{contains}%")).fetchone()
    return row["body"] if row else None


def preset_proof_paste(store: Store) -> str:
    """The same dataset spreading: anon_k pastes the exact sample rows from n1ghtcr4wl's latest Mullai post."""
    body = _latest_thread_body(store, "n1ghtcr4wl", "mullai")
    rows = _sample_lines(body) if body else []
    text = "\n".join(rows) if rows else sample_rows(random.Random(), ORGS["mullai"], n=8)
    pid = store.create_paste("Mullai Telecom proof", "anon_k", text, now().isoformat(timespec="seconds"))
    return f"paste {pid} ({'same rows as the live leak' if rows else 'fresh sample'})"


def preset_recycled_leak(store: Store) -> str:
    """Old data relabelled: data_baniya sells cybo_kaal's 18-day-old Neithal rows as a 'fresh' Palai Water dump."""
    old = _latest_thread_body(store, "cybo_kaal", "Neithal") or ""
    rows = _sample_lines(old)
    org = ORGS["palai"]
    body = ("Dear Sir/Madam,\n\nKindly note we are having FRESH Palai Water Board consumer database of 8 lakh "
            "records, extracted this week. Fields: Name, Mobile, Aadhaar, City.\n\nPrice: Rs. 1,50,000 only. "
            f"Kindly do the needful and revert back on {PERSONAS['P2'].contact}.\n\nSample for verification:\n"
            + "\n".join(rows) + "\n\nThanks and regards.")
    tid = store.create_thread(1, f"{org['name']} Consumer Database (8 lakh Records) - Fresh",
                              store.member_by_name("data_baniya")["uid"], body, now().isoformat(timespec="seconds"))
    return f"forum thread {tid} (recycled Neithal rows relabelled as Palai Water)"


def preset_delete_latest(store: Store) -> str:
    latest = store.threads(limit=1)
    if not latest:
        return "nothing to delete"
    store.delete_thread(latest[0]["tid"])
    return f"deleted forum thread {latest[0]['tid']}"


PRESETS = {
    "telecom_leak": ("Live: n1ghtcr4wl posts Mullai Telecom 1.2 crore DB", preset_telecom_leak),
    "ransom_victim": ("Live: ShadowLock lists Neithal University (72h countdown)", preset_ransom_victim),
    "ransom_deadline": ("Live: ShadowLock gives Kurinji Health 4 minutes, then publishes", preset_ransom_deadline),
    "access_sale": ("Live: volk_access sells healthcare VPN access", preset_access_sale),
    "fake_leak": ("Live: data_baniya posts a FAKE Marutham Bank leak", preset_fake_leak),
    "proof_paste": ("Live: anon_k pastes the Mullai proof rows (same dataset)", preset_proof_paste),
    "recycled_leak": ("Live: data_baniya relabels old Neithal rows as a 'fresh' Palai Water dump",
                      preset_recycled_leak),
    "delete_latest": ("Delete the latest forum thread", preset_delete_latest),
}
