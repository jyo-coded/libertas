"""Validators behind the India identifier pack and wallet extraction."""
import random

from libertas.interpres.cryptoaddr import btc_b58_info, btc_bech32_info, encode_segwit, find_wallets, tron_valid
from libertas.interpres.india import (aadhaar_candidates, gstin_valid, mobile_candidates, verhoeff_digit,
                                      verhoeff_valid)


def test_verhoeff_generation_and_validation_agree():
    r = random.Random(7)
    for _ in range(3000):
        base = "".join(r.choice("0123456789") for _ in range(11))
        assert verhoeff_valid(base + verhoeff_digit(base))
    assert verhoeff_valid("2363") and not verhoeff_valid("2364")


def test_aadhaar_rules():
    real = "23456789012" + verhoeff_digit("23456789012")
    assert aadhaar_candidates(f"id {real[:4]} {real[4:8]} {real[8:]}") == [(real, True)]
    good = "12345678901" + verhoeff_digit("12345678901")
    assert aadhaar_candidates(good, simulation=True) == [(good, True)]
    assert aadhaar_candidates(good, simulation=False) == [(good, False)]
    assert aadhaar_candidates("0123 4567 8901") == []


def test_gstin_and_mobiles():
    assert gstin_valid("27AAPFU0939F1ZV")
    assert not gstin_valid("27AAPFU0939F1ZX")
    assert mobile_candidates("+91 98765 43210 and 09876543210") == ["9876543210", "9876543210"]
    assert mobile_candidates("+91 58765 43210") == [] and mobile_candidates("+91 58765 43210", simulation=True)


def test_wallets():
    assert btc_bech32_info("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")["network"] == "mainnet"
    assert btc_bech32_info("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5") is None
    assert btc_b58_info("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2")["type"] == "P2PKH"
    assert tron_valid("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
    regtest = encode_segwit("bcrt", 0, bytes(range(20)))
    found = {w["chain"]: w for w in find_wallets(f"pay {regtest} or TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")}
    assert found["BTC"]["info"]["network"] == "regtest" and found["TRON"]["valid"]
