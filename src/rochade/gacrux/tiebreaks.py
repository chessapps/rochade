"""The tie-breaks a section may rank by.

The engine knows some sixty codes, most of them for team events or for
checking other programs. This is the individual-Swiss subset an arbiter is
likely to want, spelled in the engine's own spec syntax so the section stores
exactly what it hands over, and labelled so the standings table has headings.

`PTS` always comes first: it is the score itself, and the engine's output
puts it in the first column, which is where `compute_standings` reads it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

#: Spec -> label. Order is the order the picker offers them in.
KNOWN_TIEBREAKS: Final[dict[str, str]] = {
    "PTS": "Points",
    "BH/C1": "Buchholz Cut 1",
    "BH": "Buchholz",
    "BH/M1": "Median Buchholz",
    "SB": "Sonneborn-Berger",
    "SB/C1": "Sonneborn-Berger Cut 1",
    "DE": "Direct encounter",
    "WIN": "Wins",
    "WON": "Games won",
    "BPG": "Games with black",
    "BWG": "Wins with black",
    "PS": "Progressive score",
    "KS": "Koya",
    "AOB": "Average of opponents' Buchholz",
    "ARO": "Average rating of opponents",
    "ARO/C1": "Average rating of opponents Cut 1",
    "TPR": "Tournament performance rating",
}

#: FIDE's usual recommendation for an individual Swiss.
DEFAULT_TIEBREAKS: Final[tuple[str, ...]] = ("PTS", "BH/C1", "BH", "SB")

MAX_TIEBREAKS: Final = 9


def validate_tiebreaks(spec: Sequence[str]) -> list[str]:
    """Normalise a spec list, or raise `ValueError` saying what is wrong with it."""
    cleaned = [code.strip().upper() for code in spec]
    if not cleaned:
        raise ValueError("at least one tie-break is needed")
    if cleaned[0] != "PTS":
        raise ValueError("the first tie-break must be PTS, the points")
    if len(cleaned) > MAX_TIEBREAKS:
        raise ValueError(f"at most {MAX_TIEBREAKS} tie-breaks")
    unknown = [code for code in cleaned if code not in KNOWN_TIEBREAKS]
    if unknown:
        raise ValueError("unknown tie-break: " + ", ".join(sorted(set(unknown))))
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("a tie-break is listed twice")
    return cleaned


def label_of(spec: str) -> str:
    return KNOWN_TIEBREAKS.get(spec.strip().upper(), spec)
