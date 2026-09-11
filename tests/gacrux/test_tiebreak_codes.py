from __future__ import annotations

import pytest

from rochade.gacrux import DEFAULT_TIEBREAKS, KNOWN_TIEBREAKS, standings, validate_tiebreaks
from rochade.gacrux.tiebreaks import label_of


def test_the_default_is_fides_usual_swiss_recommendation() -> None:
    assert DEFAULT_TIEBREAKS == ("PTS", "BH/C1", "BH", "SB")
    assert validate_tiebreaks(DEFAULT_TIEBREAKS) == list(DEFAULT_TIEBREAKS)


def test_validation_normalises_case_and_whitespace() -> None:
    assert validate_tiebreaks([" pts", "bh/c1 "]) == ["PTS", "BH/C1"]


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ([], "at least one"),
        (["BH"], "must be PTS"),
        (["PTS", "XYZ"], "unknown tie-break: XYZ"),
        (["PTS", "BH", "BH"], "listed twice"),
        (["PTS", "BH", "SB", "DE", "WIN", "WON", "PS", "KS", "AOB", "ARO"], "at most 9"),
    ],
)
def test_validation_says_what_is_wrong(spec: list[str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_tiebreaks(spec)


def test_every_offered_code_has_a_label() -> None:
    assert all(KNOWN_TIEBREAKS[code] for code in KNOWN_TIEBREAKS)
    assert label_of("bh/c1") == "Buchholz Cut 1"
    assert label_of("NOPE") == "NOPE"


def test_every_offered_code_is_one_the_engine_computes(round3_text: str) -> None:
    """The allow-list is only worth having if the engine takes every entry."""
    spec = list(KNOWN_TIEBREAKS)
    rows = standings(round3_text, tiebreaks=spec, after_round=2)
    assert len(rows) == 9
    assert all(len(row.scores) == len(spec) for row in rows)
