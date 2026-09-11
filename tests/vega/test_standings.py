"""`standings.txt` as Vega 12.1.8 wrote it after round 3 of a 16-player test."""

from __future__ import annotations

import pathlib

import pytest

from rochade.vega import StandingsError, StandingsRow, looks_like_standings, parse_standings

VEGA = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "vega"


def read(name: str) -> str:
    return (VEGA / name).read_bytes().decode("utf-8")


def test_the_table_after_round_three() -> None:
    table = parse_standings(read("standings_round3.txt"))
    assert table.tournament_name == "TestOpen"
    assert table.round_no == 3
    assert table.tiebreak_codes == ("BH",)
    assert table.tiebreak_names == ("Buchholz",)
    assert len(table.rows) == 16
    assert table.rows[0] == StandingsRow(
        position=1,
        number=6,
        name="Gruber, Sarah",
        title="",
        gender="m",
        fide_rating=1922,
        national_rating=None,
        federation="AUT",
        points=2.5,
        tiebreaks=(5.0,),
    )
    # Shared positions: two players on 2.5 / 5.0 are both first, the next is third.
    assert [row.position for row in table.rows[:4]] == [1, 1, 3, 4]
    titled = next(row for row in table.rows if row.number == 1)
    assert (titled.title, titled.name) == ("FM", "Baumann, Lukas")
    wfm = next(row for row in table.rows if row.number == 3)
    assert (wfm.title, wfm.name, wfm.federation) == ("WFM", "Dubois, Elise", "FRA")
    unrated = next(row for row in table.rows if row.number == 16)
    assert (unrated.fide_rating, unrated.points, unrated.tiebreaks) == (None, 1.5, (3.5,))


def test_only_the_standings_file_looks_like_one() -> None:
    assert looks_like_standings(" Standings at round 3")
    assert not looks_like_standings(" Cross Table at round 2")
    with pytest.raises(StandingsError, match=r"not standings.txt"):
        parse_standings(read("crosstable_round2.txt"))


def test_a_broken_row_is_a_readable_error() -> None:
    text = read("standings_round3.txt").replace(
        "  1   6     Gruber, Sarah   ", "  x   6     Gruber, Sarah   "
    )
    with pytest.raises(StandingsError) as caught:
        parse_standings(text)
    assert caught.value.line_no == 8
