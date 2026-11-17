"""Cryptocurrency address detection and validation (blueprint #11, Moneta input).

BTC: Base58Check (P2PKH/P2SH, mainnet/testnet) and Bech32/Bech32m (bc, tb, bcrt=regtest).
TRON: Base58Check with version byte 0x41. ETH and XMR: format only (checksums need Keccak; flagged unverified).
"""
from __future__ import annotations

import hashlib
import re

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CONST, _BECH32M_CONST = 1, 0x2BC830A3

BTC_BECH32_RE = re.compile(r"\b((?:bc|tb|bcrt)1[02-9ac-hj-np-z]{8,87})\b")
BTC_B58_RE = re.compile(r"\b([13mn2][1-9A-HJ-NP-Za-km-z]{25,34})\b")
TRON_RE = re.compile(r"\b(T[1-9A-HJ-NP-Za-km-z]{33})\b")
ETH_RE = re.compile(r"\b(0x[a-fA-F0-9]{40})\b")
XMR_RE = re.compile(r"\b([48][0-9AB][1-9A-HJ-NP-Za-km-z]{93})\b")


def b58decode(s: str) -> bytes | None:
    n = 0
    for ch in s:
        i = B58.find(ch)
        if i < 0:
            return None
        n = n * 58 + i
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + body


def b58check_payload(s: str) -> bytes | None:
    raw = b58decode(s)
    if not raw or len(raw) < 5:
        return None
    payload, check = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != check:
        return None
    return payload


def _polymod(values):
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= gen[i] if (b >> i) & 1 else 0
    return chk


def _hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def convertbits(data, frombits, tobits, pad=True):
    acc, bits, ret, maxv = 0, 0, [], (1 << tobits) - 1
    for value in data:
        if value < 0 or value >> frombits:
            return None
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    elif not pad and (bits >= frombits or ((acc << (tobits - bits)) & maxv)):
        return None
    return ret


def bech32_decode(addr: str):
    if addr.lower() != addr and addr.upper() != addr:
        return None
    addr = addr.lower()
    pos = addr.rfind("1")
    if pos < 1 or pos + 7 > len(addr) or len(addr) > 90 or any(c not in BECH32_CHARSET for c in addr[pos + 1:]):
        return None
    hrp, data = addr[:pos], [BECH32_CHARSET.find(c) for c in addr[pos + 1:]]
    const = _polymod(_hrp_expand(hrp) + data)
    spec = "bech32" if const == _BECH32_CONST else "bech32m" if const == _BECH32M_CONST else None
    return (hrp, data[:-6], spec) if spec else None


def bech32_encode(hrp: str, data: list[int], spec: str) -> str:
    const = _BECH32M_CONST if spec == "bech32m" else _BECH32_CONST
    pm = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ const
    return hrp + "1" + "".join(BECH32_CHARSET[d] for d in data + [(pm >> 5 * (5 - i)) & 31 for i in range(6)])


def encode_segwit(hrp: str, witver: int, program: bytes) -> str:
    return bech32_encode(hrp, [witver] + convertbits(program, 8, 5), "bech32" if witver == 0 else "bech32m")


BTC_NETWORKS = {"bc": "mainnet", "tb": "testnet", "bcrt": "regtest"}


def btc_bech32_info(addr: str) -> dict | None:
    dec = bech32_decode(addr)
    if not dec or dec[0] not in BTC_NETWORKS or not dec[1]:
        return None
    hrp, data, spec = dec
    witver, prog = data[0], convertbits(data[1:], 5, 8, False)
    if prog is None or not 2 <= len(prog) <= 40 or witver > 16:
        return None
    if (witver == 0 and (spec != "bech32" or len(prog) not in (20, 32))) or (witver > 0 and spec != "bech32m"):
        return None
    return {"network": BTC_NETWORKS[hrp], "type": f"segwit v{witver}"}


def btc_b58_info(addr: str) -> dict | None:
    payload = b58check_payload(addr)
    if not payload or len(payload) != 21:
        return None
    return {0x00: {"network": "mainnet", "type": "P2PKH"}, 0x05: {"network": "mainnet", "type": "P2SH"},
            0x6F: {"network": "testnet", "type": "P2PKH"}, 0xC4: {"network": "testnet", "type": "P2SH"}}.get(payload[0])


def tron_valid(addr: str) -> bool:
    payload = b58check_payload(addr)
    return bool(payload and len(payload) == 21 and payload[0] == 0x41)


def find_wallets(text: str) -> list[dict]:
    """[{chain, address, valid (True/False/None=unverifiable), info}] deduplicated."""
    found: dict[tuple[str, str], dict] = {}
    for m in BTC_BECH32_RE.finditer(text):
        info = btc_bech32_info(m.group(1))
        found.setdefault(("BTC", m.group(1).lower()), {"chain": "BTC", "address": m.group(1).lower(),
                                                       "valid": info is not None, "info": info or {}})
    for m in BTC_B58_RE.finditer(text):
        info = btc_b58_info(m.group(1))
        if info:
            found.setdefault(("BTC", m.group(1)), {"chain": "BTC", "address": m.group(1), "valid": True, "info": info})
    for m in TRON_RE.finditer(text):
        if tron_valid(m.group(1)):
            found.setdefault(("TRON", m.group(1)), {"chain": "TRON", "address": m.group(1), "valid": True,
                                                    "info": {"network": "mainnet"}})
    for m in ETH_RE.finditer(text):
        addr = m.group(1)
        checksum_free = addr[2:] == addr[2:].lower() or addr[2:] == addr[2:].upper()
        found.setdefault(("ETH", addr.lower()), {"chain": "ETH", "address": addr, "valid": True if checksum_free else None,
                                                 "info": {"note": "EIP-55 checksum not verified"}})
    for m in XMR_RE.finditer(text):
        found.setdefault(("XMR", m.group(1)), {"chain": "XMR", "address": m.group(1), "valid": None,
                                               "info": {"note": "format only; Monero hides on-chain flows"}})
    return list(found.values())
