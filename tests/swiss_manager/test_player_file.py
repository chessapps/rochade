"""Reading the Swiss-Manager player file.

The fixtures are real: `Extras -> Daten Import/Export -> Spielerdaten
(Text-File)` out of a 100-player test tournament on 15.0.0.3, cut down to the
players of six boards.
"""

from __future__ import annotations

import pathlib

import pytest

from seebach.swiss_manager import (
    PlayerFileError,
    by_start_number,
    looks_like_player_file,
    parse_player_file,
)

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "swiss_manager"


@pytest.fixture
def players_text() -> str:
    return (FIXTURES / "players_round1.txt").read_bytes().decode("utf-8")


def test_a_real_export_reads(players_text: str) -> None:
    players = by_start_number(parse_player_file(players_text))

    assert len(players) == 14
    first = players[1]
    assert first.name == "Brunner,Livia"
    assert first.title == "WGM"
    assert first.rating == 2447
    assert first.federation == "SUI"
    # No FIDE ids in this tournament; an empty cell must not become "0".
    assert first.fide_id == ""


def test_the_standings_ride_along(players_text: str) -> None:
    """Pkt, Wtg1.. and Rang are Swiss-Manager's own table, as of the export."""
    players = by_start_number(parse_player_file(players_text))

    assert players[1].points == 1.0
    assert players[1].tiebreaks == (1.0,)
    assert players[1].rank == 1
    assert players[2].points == 0.0
    assert players[2].rank == 61


def test_a_half_point_reads_with_either_decimal_mark() -> None:
    text = "\r\n".join(
        [
            "Nr;Nachname;Vorname;Pkt;Wtg1;Wtg2;Wtg3;Rang",
            "7;Iten;Nadia;2,5;13,5;;;3",
            "8;Keller;Urs;2.5;12.0;9;;4",
            "",
        ]
    )
    players = by_start_number(parse_player_file(text))

    assert players[7].points == 2.5
    assert players[7].tiebreaks == (13.5,)
    assert players[8].tiebreaks == (12.0, 9.0)
    assert players[8].rank == 4


def test_a_list_without_standings_columns_has_none() -> None:
    text = "\r\n".join(["Nr;Nachname;Vorname", "1;Iten;Nadia", ""])
    player = parse_player_file(text)[0]
    assert player.points is None
    assert player.tiebreaks == ()
    assert player.rank is None


def test_columns_are_found_by_name_not_by_position() -> None:
    """The number of tiebreak columns follows the tournament's settings."""
    text = "Nr;Nachname;Vorname;EloInt;Fed;Titel\r\n7;Iten;Nadia;1804;SUI;WFM\r\n"

    player = parse_player_file(text)[0]

    assert (player.start_number, player.name, player.rating) == (7, "Iten,Nadia", 1804)


def test_a_national_rating_stands_in_when_there_is_no_international_one() -> None:
    text = "Nr;Nachname;Vorname;EloNat;EloInt\r\n3;Huber;Marco;1755;0\r\n"

    assert parse_player_file(text)[0].rating == 1755


def test_a_player_with_no_rating_at_all_has_none() -> None:
    text = "Nr;Nachname;Vorname;EloNat;EloInt\r\n3;Huber;Marco;0;0\r\n"

    assert parse_player_file(text)[0].rating is None


def test_another_file_is_refused_by_its_header() -> None:
    with pytest.raises(PlayerFileError) as caught:
        parse_player_file("Runde;Brett;IdentW;IdentS;NrW;NrS\r\n1;1;0;0;1;2\r\n")

    assert "header" in str(caught.value)
    assert caught.value.line_no == 1


def test_a_header_with_no_players_is_refused() -> None:
    with pytest.raises(PlayerFileError):
        parse_player_file("Nr;Nachname;Vorname\r\n")


def test_the_sniffer_tells_the_two_text_files_apart(players_text: str) -> None:
    assert looks_like_player_file(players_text)
    assert not looks_like_player_file("Runde;Brett;IdentW;IdentS;NrW;NrS\r\n")
