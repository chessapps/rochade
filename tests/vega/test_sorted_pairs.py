"""`SortedPairs.txt` as Vega 12.1.8 wrote it: every board twice, the bye against BYE."""

from __future__ import annotations

import pathlib

import pytest

from rochade.vega import SortedPair, SortedPairsError, parse_sorted_pairs

VEGA = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "vega"


def read(name: str) -> str:
    return (VEGA / name).read_bytes().decode("utf-8")


def test_round_three_as_vega_paired_it() -> None:
    pairs = parse_sorted_pairs(read("sorted_pairs_round3.txt"))
    assert pairs.tournament_name == "Rochade M0 Spike"
    assert pairs.round_no == 3
    assert pairs.boards == (
        SortedPair(1, "Mueller, Tobias", "Chen, Wei"),
        SortedPair(2, "Baumann, Lukas", "Dubois, Elise"),
        SortedPair(3, "Huber, Marco", "Jenni, Rafael"),
        SortedPair(4, "Fischer, Jonas", "Iten, Nadia"),
        SortedPair(5, "Gruber, Sarah", None),
    )
    assert pairs.boards[4].is_bye


def test_the_file_after_a_manual_change_carries_the_change_and_the_accents() -> None:
    """Boards 3 and 4 were swapped by hand in the Manual Pairing dialog.

    `engine_round3_stale_after_manual.man` beside it still shows the engine's
    original 7-9 and 5-8: that file is not rewritten, this one is.
    """
    pairs = parse_sorted_pairs(read("sorted_pairs_round3_manual_accents.txt"))
    assert pairs.tournament_name == "Rochade M0 Spike"
    by_board = {p.board: p for p in pairs.boards}
    assert by_board[3] == SortedPair(3, "Huber, Marco", "Iten, Nadia")
    assert by_board[4] == SortedPair(4, "Jenni, Rafael", "Fischer, Jonas")
    assert by_board[1].white == "Müller, Tobias"
    assert by_board[2].black == "Dubois, Élise"
    stale = read("engine_round3_stale_after_manual.man").split()
    assert stale[5:9] == ["7", "9", "5", "8"]


def test_the_late_comer_is_paired_and_nobody_has_the_bye() -> None:
    pairs = parse_sorted_pairs(read("sorted_pairs_round4_latecomer.txt"))
    assert pairs.round_no == 4
    assert not any(p.is_bye for p in pairs.boards)
    assert pairs.boards[-1] == SortedPair(5, "Iten, Nadia", "Keller, Simon")


def test_a_board_listed_with_two_different_pairs_is_refused() -> None:
    text = read("sorted_pairs_round3.txt").replace(
        "Huber, Marco          plays with white VS         Jenni, Rafael          in board    3",
        "Huber, Marco          plays with white VS         Jenni, Rafael          in board    4",
    )
    with pytest.raises(SortedPairsError, match="board 4 is listed twice"):
        parse_sorted_pairs(text)


def test_not_a_pairing_list() -> None:
    with pytest.raises(SortedPairsError, match="Pairing of round"):
        parse_sorted_pairs("012 Something\n001    1 ...")
