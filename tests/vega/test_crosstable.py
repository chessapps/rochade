"""`crosstable.txt` as Vega 12.1.8 wrote it during the spike, read cell by cell."""

from __future__ import annotations

import pathlib

import pytest

from rochade.vega import CrossTableError, parse_cross_table

VEGA = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "vega"


def read(name: str) -> str:
    return (VEGA / name).read_bytes().decode("utf-8")


def test_the_players_and_their_history_after_two_rounds() -> None:
    table = parse_cross_table(read("crosstable_round2.txt"))
    assert table.tournament_name == "Rochade M0 Spike"
    assert table.round_no == 2
    rows = {row.number: row for row in table.rows}
    assert len(rows) == 9

    baumann = rows[1]
    assert (baumann.name, baumann.rating, baumann.title, baumann.federation, baumann.points) == (
        "Baumann, Lukas",
        2201,
        "FM",
        "SUI",
        1.5,
    )
    assert [(c.result, c.colour, c.opponent) for c in baumann.cells] == [
        ("1", "w", 5),
        ("=", "b", 2),
    ]
    # No title, no problem: the title column is simply blank.
    assert (rows[2].title, rows[2].federation) == ("", "SUI")
    assert (rows[3].title, rows[3].federation) == ("WFM", "FRA")


def test_forfeits_and_byes_are_the_trf_codes() -> None:
    rows = {row.number: row for row in parse_cross_table(read("crosstable_round2.txt")).rows}
    # +F8: a forfeit win over 8; Vega prints F where the colour would be.
    forfeit = rows[4].cells[0]
    assert (forfeit.raw, forfeit.result, forfeit.colour, forfeit.opponent) == ("+F8", "+", "-", 8)
    loss = rows[8].cells[0]
    assert (loss.raw, loss.result, loss.opponent) == ("-F4", "-", 4)
    # +PAB is the pairing-allocated bye, =HPB the half-point bye.
    assert (rows[9].cells[0].raw, rows[9].cells[0].result, rows[9].cells[0].opponent) == (
        "+PAB",
        "U",
        None,
    )
    assert (rows[5].cells[1].raw, rows[5].cells[1].result) == ("=HPB", "H")
    assert parse_cross_table(read("crosstable_round2.txt")).unknown_cells == []


def test_a_late_comer_has_dashes_for_the_rounds_missed_and_no_rating() -> None:
    table = parse_cross_table(read("crosstable_latecomer.txt"))
    keller = table.rows[-1]
    assert (keller.number, keller.name, keller.rating, keller.points) == (
        10,
        "Keller, Simon",
        None,
        0.0,
    )
    assert [c.raw for c in keller.cells] == ["--", "--", "--"]
    assert all(c.is_absent for c in keller.cells)


def test_accented_names_come_through_as_written() -> None:
    rows = {row.number: row for row in parse_cross_table(read("crosstable_accents.txt")).rows}
    assert rows[3].name == "Dubois, Élise"
    assert rows[4].name == "Müller, Tobias"


def test_an_unknown_cell_is_kept_not_guessed() -> None:
    text = read("crosstable_round2.txt").replace("+PAB ", "+XYZ ")
    table = parse_cross_table(text)
    cell = next(c for row in table.rows for c in row.cells if c.raw == "+XYZ")
    assert cell.known is False and cell.result == " "
    assert table.unknown_cells == ["+XYZ"]


def test_not_a_cross_table() -> None:
    with pytest.raises(CrossTableError, match="Cross Table at round"):
        parse_cross_table("Runde;Brett;IdentW\n1;1;0")
    with pytest.raises(CrossTableError, match="no player rows"):
        parse_cross_table(" Cross Table at round 1\n\n  N NAME  Rtg   T  Fed  Pts |   1\n----\n")
