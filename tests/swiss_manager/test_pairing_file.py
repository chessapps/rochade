"""The Swiss-Manager pairing file, proved against files Swiss-Manager wrote.

Every fixture under `tests/fixtures/swiss_manager/` came out of Swiss-Manager
15.0.0.3 during M0, or went into it and was accepted. That is the bar: what we
render must be byte-identical to what it exported, and what it exported must
read back as the results we know were on the boards.
"""

from __future__ import annotations

import pathlib

import pytest

from seebach.swiss_manager import (
    PairingFileError,
    PairingLine,
    parse_pairing_file,
    render_pairing_file,
)

SM = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "swiss_manager"


def read(name: str) -> str:
    return (SM / name).read_bytes().decode("utf-8")


def test_a_played_round_reads_back_with_every_code() -> None:
    lines = parse_pairing_file(read("pairings_rounds1-2_played.txt"))
    round1 = [line for line in lines if line.round_no == 1]
    assert [(line.board, line.white, line.black) for line in round1] == [
        (1, 1, 5),
        (2, 6, 2),
        (3, 3, 7),
        (4, 4, 8),
        (5, 9, None),
    ]
    assert [(line.white_result, line.black_result) for line in round1[:4]] == [
        ("1", "0"),
        ("0", "1"),
        ("=", "="),
        ("+", "-"),  # Kontumaz K
    ]
    assert round1[4].is_bye


def test_an_unplayed_round_reads_as_blank_boards() -> None:
    lines = parse_pairing_file(read("pairings_round3_unplayed.txt"))
    assert all(line.white_result == " " for line in lines)
    assert [line.white for line in lines] == [4, 1, 7, 5, 6]


def test_swiss_managers_own_export_round_trips_byte_for_byte() -> None:
    """Rendering what we parsed reproduces the file, unplayed rows included."""
    text = read("pairings_round3_unplayed.txt")
    assert render_pairing_file(parse_pairing_file(text)) == text


def test_rendering_reproduces_the_file_swiss_manager_accepted() -> None:
    """`pairings_round4_we_wrote.txt` was imported and scored as intended.

    It carries a win, a draw, a double forfeit, a forfeit for black and the bye
    row -- the whole outbound vocabulary in one file.
    """
    lines = [
        PairingLine(4, 1, 4, 1, "0", "1"),
        PairingLine(4, 2, 9, 3, "=", "="),
        PairingLine(4, 3, 2, 5, "-", "-"),
        PairingLine(4, 4, 6, 7, "-", "+"),
        PairingLine(4, 5, 8, None),
    ]
    assert render_pairing_file(lines) == read("pairings_round4_we_wrote.txt")


def test_a_scored_bye_still_reads_as_a_bye() -> None:
    """After the round Swiss-Manager rewrites the bye row as 1;1;;1:1."""
    lines = parse_pairing_file(read("pairings_rounds3-4_played.txt"))
    byes = [line for line in lines if line.is_bye]
    assert [(line.round_no, line.white) for line in byes] == [(3, 6), (4, 8)]


def test_a_bye_is_written_as_unplayed_whatever_we_hold_for_it() -> None:
    line = PairingLine(3, 5, 6, None, white_result="U")
    assert render_pairing_file([line]).splitlines()[1] == "3;5;0;0;6;-1;0;0;;0:0;0;;"


def test_a_result_the_file_cannot_carry_is_refused_not_guessed() -> None:
    with pytest.raises(PairingFileError, match="cannot express"):
        render_pairing_file([PairingLine(1, 1, 1, 2, "W", "L")])
    with pytest.raises(PairingFileError, match="cannot express"):
        render_pairing_file([PairingLine(1, 1, 1, 2, "1", "1")])


def test_a_foreign_file_is_rejected_by_its_header() -> None:
    with pytest.raises(PairingFileError, match="header"):
        parse_pairing_file("012 Some tournament\r\n001    1 ...\r\n")
