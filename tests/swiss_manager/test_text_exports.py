"""The two text exports read as one round.

Both fixtures came out of the same Swiss-Manager tournament on 15.0.0.3, which
is the only way this pair means anything: the pairing file names nobody and the
player file pairs nobody.
"""

from __future__ import annotations

import pathlib

import pytest

from seebach.interchange import manager_for
from seebach.interchange.formats import swiss_manager_text
from seebach.interchange.port import InterchangeError

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "swiss_manager"


@pytest.fixture
def players() -> str:
    return (FIXTURES / "players_round1.txt").read_bytes().decode("utf-8")


@pytest.fixture
def pairings() -> str:
    return (FIXTURES / "pairings_round1_played.txt").read_bytes().decode("utf-8")


def test_the_two_files_join_on_the_start_number(players: str, pairings: str) -> None:
    document = swiss_manager_text.read_document(players + "\n" + pairings)

    assert document.rounds_present == 1
    assert len(document.players) == 14
    boards = document.board_rows(1)
    assert [row.board for row in boards] == [1, 2, 3, 4, 5, 6, 7]
    first = boards[0]
    assert (first.white_name, first.black_name) == ("Brunner,Livia", "Novak,Tomasz")
    assert (first.white_result, first.black_result) == ("1", "0")


def test_either_file_may_come_first(players: str, pairings: str) -> None:
    one = swiss_manager_text.read_document(players + "\n" + pairings)
    other = swiss_manager_text.read_document(pairings + "\n" + players)

    assert one.players == other.players
    assert one.board_rows(1) == other.board_rows(1)


def test_a_forfeit_survives_the_join(players: str, pairings: str) -> None:
    document = swiss_manager_text.read_document(players + "\n" + pairings)

    forfeits = [
        row for row in document.board_rows(1) if (row.white_result, row.black_result) == ("+", "-")
    ]
    assert len(forfeits) == 1


def test_a_bye_carries_the_code_swiss_manager_does_not_write(players: str) -> None:
    """`NrS = -1` is a pairing-allocated bye; what it is worth is a setting there."""
    pairings = (
        "Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS\r\n"
        "1;1;0;0;1;-1;0;0;;0:0;0;;\r\n"
    )

    row = swiss_manager_text.read_document(players + "\n" + pairings).board_rows(1)[0]

    assert row.is_bye
    assert row.white_result == "U"
    assert row.black_name is None


def test_the_pairing_file_on_its_own_says_what_is_missing(pairings: str) -> None:
    with pytest.raises(InterchangeError) as caught:
        swiss_manager_text.read_document(pairings)

    assert "Spielerdaten" in str(caught.value)


def test_the_player_file_on_its_own_says_what_is_missing(players: str) -> None:
    with pytest.raises(InterchangeError) as caught:
        swiss_manager_text.read_document(players)

    assert "Spielerauslosung" in str(caught.value)


def test_files_from_two_different_tournaments_are_caught(pairings: str) -> None:
    """A start number the player file does not have is not a board we can show."""
    players = "Nr;Nachname;Vorname;EloInt;Fed\r\n1;Brunner;Livia;2447;SUI\r\n"

    with pytest.raises(InterchangeError) as caught:
        swiss_manager_text.read_document(players + "\n" + pairings)

    assert "the same tournament" in str(caught.value)


def test_the_adapter_reads_the_pair_and_still_reads_trf(players: str, pairings: str) -> None:
    """Rounds imported before this change are re-read from their stored source."""
    manager = manager_for("swiss_manager")
    trf = (FIXTURES / "round3_paired.trf").read_bytes().decode("utf-8")

    assert manager.read_round(players + "\n" + pairings).rounds_present == 1
    assert manager.read_round(trf).rounds_present == 3


def test_a_round_of_a_document_can_be_written_back(players: str, pairings: str) -> None:
    """The whole point: what came in as two files goes back as one pairing file."""
    from seebach.interchange.document import ResultEntry

    manager = manager_for("swiss_manager")
    document = manager.read_round(players + "\n" + pairings)
    results = [
        ResultEntry(white_rank=row.white_rank, white_result="=", black_result="=")
        for row in document.board_rows(1)
        if not row.is_bye
    ]

    written = manager.write_results(document, 1, results, stem="round1")

    assert written.filename.endswith(".txt")
    assert "0,5;0,5" in written.content
