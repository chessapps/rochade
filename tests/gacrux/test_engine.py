"""The vendored engine, driven the way the application drives it.

No mocks: every test here runs the real TieBreakServer scripts in a child
process, because the wrapper's whole job is the seam between our process and
theirs, and a fake on our side of it would prove nothing. The golden files
under `tests/fixtures/gacrux/` pin what the engine said the day it was
vendored; if a refresh moves them, that is a fact to record, not a test to
silence.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rochade.gacrux import EngineError, EnginePair, engine_dir, pair, standings
from rochade.platform.config import Settings

GOLDEN = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "gacrux"


def _golden(name: str) -> dict[str, object]:
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _boards(pairs: list[EnginePair]) -> list[list[int]]:
    """The golden files' shape: the bye is black 0, as the engine writes it."""
    return [[p.white, p.black or 0] for p in pairs]


def test_the_packaged_engine_is_where_the_default_points(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROCHADE_GACRUX_DIR", raising=False)
    from rochade.platform import config

    config.settings.cache_clear()
    assert (engine_dir() / "pairingchecker.py").is_file()
    assert (engine_dir() / "LICENSE").is_file()


def test_the_engine_dir_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROCHADE_GACRUX_DIR", "/nowhere/engine")
    assert str(Settings().gacrux_dir).endswith("engine")


# --- pairing ----------------------------------------------------------------


def test_round_one_of_the_seed_reproduces_the_fixtures_boards(round1_text: str) -> None:
    """The fixture was paired by hand in FIDE order; the engine agrees with it."""
    pairs = pair(round1_text, round_no=1, top_colour="white")
    assert _boards(pairs) == _golden("round1_pairs.json")["pairs"]


def test_top_colour_black_flips_every_board(round1_text: str) -> None:
    fresh = "\r\n".join(
        line[:89] if line.startswith("001") else line for line in round1_text.split("\r\n")
    )
    white = pair(fresh, round_no=1, top_colour="white")
    black = pair(fresh, round_no=1, top_colour="black")
    assert [(p.black, p.white) for p in black] == [(p.white, p.black) for p in white]


def test_round_three_of_the_messy_seed_matches_the_golden(round3_text: str) -> None:
    pairs = pair(round3_text, round_no=3)
    assert _boards(pairs) == _golden("round3_pairs.json")["pairs"]
    # Player 9 is marked Z (absent) for round 3 and is left out.
    assert all(9 not in (p.white, p.black) for p in pairs)


def test_an_odd_field_gets_a_pairing_allocated_bye(round3_text: str) -> None:
    pairs = pair(round3_text, round_no=3, unpaired=[8])
    assert _boards(pairs) == _golden("round3_pairs_without_8.json")["pairs"]
    byes = [p for p in pairs if p.is_bye]
    assert len(byes) == 1
    assert byes[0] == EnginePair(white=6, black=None)
    assert all(8 not in (p.white, p.black) for p in pairs)


def test_pairing_past_the_declared_rounds_is_refused(round3_text: str) -> None:
    short = round3_text.replace("XXR 5", "XXR 2")
    with pytest.raises(EngineError) as excinfo:
        pair(short, round_no=3)
    assert excinfo.value.code == 504
    assert "can't pair round 3" in excinfo.value.errors[0]


def test_a_damaged_file_comes_back_as_the_engines_own_message() -> None:
    with pytest.raises(EngineError) as excinfo:
        pair("012 Broken\r\n001 abc\r\n", round_no=1)
    assert excinfo.value.code == 502
    assert any("line 2" in line for line in excinfo.value.errors)


def test_a_missing_engine_is_a_clear_error(tmp_path: pathlib.Path, round1_text: str) -> None:
    with pytest.raises(EngineError, match="not installed"):
        pair(round1_text, round_no=1, engine=tmp_path)


def test_a_hang_is_cut_off(round1_text: str) -> None:
    with pytest.raises(EngineError, match="did not finish"):
        pair(round1_text, round_no=1, timeout=0.001)


def test_the_wrapper_validates_its_own_arguments(round1_text: str) -> None:
    with pytest.raises(ValueError):
        pair(round1_text, round_no=0)
    with pytest.raises(ValueError):
        pair(round1_text, round_no=1, top_colour="red")
    with pytest.raises(ValueError, match="PTS"):
        standings(round1_text, tiebreaks=["BH"])


# --- standings --------------------------------------------------------------


def test_standings_after_two_rounds_match_the_golden(round3_text: str) -> None:
    rows = standings(round3_text, tiebreaks=["PTS", "BH/C1", "BH", "SB"], after_round=2)
    got = [[r.start_rank, r.rank, list(r.scores)] for r in rows]
    assert got == _golden("round3_standings_after_2.json")["rows"]


def test_standings_are_sorted_by_rank_then_start_number(round3_text: str) -> None:
    rows = standings(round3_text, tiebreaks=["PTS", "BH/C1", "BH", "SB"], after_round=2)
    assert [(r.rank, r.start_rank) for r in rows] == sorted((r.rank, r.start_rank) for r in rows)
    leader = rows[0]
    assert leader.start_rank == 1
    assert leader.points == 2.0
    assert leader.tiebreaks == (1.0, 2.0, 2.0)


def test_a_blank_round_block_scores_like_an_absence(round3_text: str) -> None:
    """A late entry's missing rounds can be left blank: the engine reads them as Z."""
    lines = []
    for line in round3_text.split("\r\n"):
        if line.startswith("001") and int(line[4:8]) == 9:
            line = line[:91] + " " * 10 + line[101:]
        lines.append(line)
    blank = "\r\n".join(lines)
    spec = ["PTS", "BH/C1", "BH", "SB"]
    assert standings(blank, tiebreaks=spec, after_round=2) == standings(
        round3_text, tiebreaks=spec, after_round=2
    )
