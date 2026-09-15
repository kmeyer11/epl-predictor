"""Normalizes team names so the same club matches across data providers that
spell it differently (e.g. TheSportsDB's "Silkeborg IF" vs football-data.co.uk's
"Silkeborg"). Used only to *match* records between sources - display strings
from the API response are always what gets printed.
"""
import re

_TRANSLATE = str.maketrans(
    {"æ": "ae", "Æ": "Ae", "ø": "o", "Ø": "O", "å": "aa", "Å": "Aa"}
)
# Generic club-type words, plus a few specific club initialisms (e.g. AGF for
# Aarhus) that one provider includes and another drops.
_CLUB_WORDS = {"fc", "bk", "if", "gf", "ac", "afc", "sk", "ff", "cf", "agf"}


def normalize_team(name):
    folded = name.translate(_TRANSLATE)
    words = [w for w in re.findall(r"[A-Za-z0-9]+", folded) if w.lower() not in _CLUB_WORDS]
    return " ".join(words).lower().strip()
