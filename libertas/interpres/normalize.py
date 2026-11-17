"""Anti-obfuscation normalisation (blueprint #15): NFKC, zero-width stripping, homoglyph folding, leet folding."""
from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = re.compile("[​-‏⁠-⁤﻿­᠎]")
CONFUSABLES = str.maketrans({
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d",
    "һ": "h", "ӏ": "l", "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "Х": "X", "І": "I",
    # Greek
    "α": "a", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
})
_LEET_BASE = {"0": "o", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "l"}
LEET = str.maketrans({**_LEET_BASE, "1": "i"})        # 'pr1ce' -> 'price'
LEET_L = str.maketrans({**_LEET_BASE, "1": "l"})      # 'mu11ai' -> 'mullai'
_TOKEN = re.compile(r"[a-z0-9@$!|]+")


def normalize(text: str) -> str:
    """Lower-cased, NFKC-normalised text with invisible characters removed and homoglyphs folded."""
    t = unicodedata.normalize("NFKC", text or "")
    t = ZERO_WIDTH.sub("", t)
    return t.translate(CONFUSABLES).lower()


def deleet(norm: str, table=LEET) -> str:
    """Fold leetspeak inside tokens that mix letters with leet characters ('mull4i' -> 'mullai').
    Pure numbers are left alone so amounts and identifiers survive."""
    def fix(m: re.Match) -> str:
        tok = m.group(0)
        if re.search(r"[a-z]", tok) and re.search(r"[013457@$!|]", tok):
            return tok.translate(table)
        return tok
    return _TOKEN.sub(fix, norm)


def deleet_variants(norm: str) -> list[str]:
    """'1' can stand for 'i' or 'l', so both readings are produced."""
    return list(dict.fromkeys([deleet(norm, LEET), deleet(norm, LEET_L)]))
