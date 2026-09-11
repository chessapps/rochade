"""The Vega round, end to end, on the files Vega actually wrote.

`crosstable_round2.txt` and `sorted_pairs_round3.txt` are what Vega 12.1.8
left in the tournament folder after pairing round 3 of the spike tournament.
`round3_filled_we_wrote.trf` is the file Vega then imported, scored, and
paired round 4 on. The tests below hand over the one pair, enter the same
results, and assert the export is that file -- and that round 4's list, with
a late-comer, comes in on the roster we already hold.
"""

from __future__ import annotations

import pathlib

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.games.claim_result import ClaimResult
from rochade.features.games.set_result import SetResult
from rochade.features.imports.import_round import ImportRound
from rochade.features.imports.preview_import import PreviewImport
from rochade.features.rounds.export_round import ExportRound
from rochade.features.rounds.release_round import ReleaseRound
from rochade.features.standings.import_standings import ImportStandings
from rochade.interchange import InterchangeError, manager_for
from rochade.platform.errors import ValidationFailed
from rochade.shared.enums import GameResult, RoundState
from rochade.shared.models import Round, Section, Tournament
from rochade.trf import parse
from tests.conftest import Send
from tests.handlers.test_result_flow import device_of

pytestmark = [pytest.mark.db, pytest.mark.manager("vega")]

VEGA = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "vega"


def read(name: str) -> str:
    return (VEGA / name).read_bytes().decode("utf-8")


def round_three() -> str:
    return read("crosstable_round2.txt") + "\n" + read("sorted_pairs_round3.txt")


def test_preview_reads_the_folder_files_as_round_3_with_history(
    send: Send, tournament: Tournament
) -> None:
    plan = send(
        PreviewImport(
            tournament_id=tournament.id,
            section_name="A",
            content=round_three(),
            declared_rounds=5,
        )
    )
    assert plan.tournament_name == "Rochade M0 Spike"
    assert plan.file_round == 3
    assert plan.declared_rounds == 5  # the arbiter's answer: Vega's files do not say
    assert plan.boards == 4
    assert plan.byes == 1
    assert len(plan.players_added) == 9
    assert plan.unknown_result_codes == []


def test_boards_carry_vegas_numbers_and_history_carries_its_codes(
    send: Send, session: Session, tournament: Tournament
) -> None:
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=round_three(),
            declared_rounds=5,
        )
    )
    rounds = {r.number: r for r in session.scalars(select(Round)).all()}
    boards = sorted(rounds[3].games, key=lambda g: g.board)
    # Straight off SortedPairs.txt, which Vega wrote from the same pairing.
    assert [(g.board, g.white_rank, g.black_rank) for g in boards] == [
        (1, 4, 2),
        (2, 1, 3),
        (3, 7, 9),
        (4, 5, 8),
        (5, 6, None),
    ]
    assert boards[0].white_name == "Mueller, Tobias"
    assert all(g.white_result == " " for g in boards[:4])
    assert boards[4].white_result == "U"

    # Round 1 from the cross table: the forfeit (+F8 / -F4) and the bye (+PAB).
    first = {
        (g.white_rank, g.black_rank): (g.white_result, g.black_result) for g in rounds[1].games
    }
    assert first[(4, 8)] == ("+", "-")
    assert first[(9, None)] == ("U", " ")
    second = {
        (g.white_rank, g.black_rank): (g.white_result, g.black_result) for g in rounds[2].games
    }
    assert second[(5, None)] == ("H", " ")

    section = session.scalars(select(Section)).one()
    assert section.declared_rounds == 5


def test_the_export_is_the_file_vega_imported_and_paired_on(
    send: Send, session: Session, tournament: Tournament
) -> None:
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=round_three(),
            declared_rounds=5,
        )
    )
    round_ = session.scalars(select(Round).where(Round.number == 3)).one()
    boards = {g.board: g for g in round_.games}
    phone = device_of(tournament, "a")

    send(ClaimResult(game_id=boards[1].id, result=GameResult.WHITE_WIN), principal=phone)
    send(ClaimResult(game_id=boards[2].id, result=GameResult.DRAW), principal=phone)
    send(ClaimResult(game_id=boards[3].id, result=GameResult.BLACK_WIN), principal=phone)
    send(SetResult(game_id=boards[4].id, white_result="+", black_result="-"))
    send(ReleaseRound(round_id=round_.id))

    exported = send(ExportRound(round_id=round_.id))
    assert exported.manager == "vega"
    assert exported.file_format == "trf16 for Vega"
    # The same name every round: Vega replaces its tournament with the file
    # and names it after the stem, so `A.vegz` stays `A.vegz`.
    assert exported.filename == "A.trf"
    assert exported.boards_written == 4
    assert "TRF2026" in exported.next_step

    ours = parse(exported.content)
    theirs = parse(read("round3_filled_we_wrote.trf"))
    assert ours.declared_rounds == theirs.declared_rounds == 5
    for rank, player in theirs.players.items():
        mine = ours.players[rank]
        assert mine.name == player.name
        assert mine.points == player.points
        assert {r: (e.opponent, e.colour, e.result) for r, e in mine.rounds.items()} == {
            r: (e.opponent, e.colour, e.result) for r, e in player.rounds.items()
        }
    assert "142 5" in exported.content.split("\r\n")


def test_round_four_comes_in_as_the_pairing_list_alone(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """From the second round on the roster we hold names the boards."""
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=round_three(),
            declared_rounds=5,
        )
    )
    third = session.scalars(select(Round).where(Round.number == 3)).one()
    send(ReleaseRound(round_id=third.id, force=True))
    send(ExportRound(round_id=third.id, force=True))

    plan = send(
        PreviewImport(
            tournament_id=tournament.id,
            section_name="A",
            content=read("sorted_pairs_round4.txt"),
        )
    )
    assert plan.file_round == 4
    assert plan.players_added == [] and plan.players_removed == []
    assert plan.declared_rounds == 5  # remembered on the section

    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=read("sorted_pairs_round4.txt"),
        )
    )
    fourth = session.scalars(select(Round).where(Round.number == 4)).one()
    games = sorted(fourth.games, key=lambda g: g.board)
    assert [(g.board, g.white_rank, g.black_rank) for g in games] == [
        (1, 4, 1),
        (2, 9, 3),
        (3, 2, 5),
        (4, 6, 7),
        (5, 8, None),
    ]
    # The rounds the list says nothing about are untouched: the history that
    # came with round 3, and round 3 itself as Rochade ran it.
    earlier = {r.number: r for r in fourth.section.rounds if r.number < 4}
    assert sorted(earlier) == [1, 2, 3]
    assert len(earlier[1].games) == 5 and len(earlier[2].games) == 5
    assert earlier[3].state is RoundState.EXPORTED
    assert len(earlier[3].games) == 5


def test_a_round_imported_from_the_pairing_list_alone_exports_with_its_history(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """Vega replaces its tournament with the file we hand back, so the file
    must carry every round -- the pairing list it came from carried none."""
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=round_three(),
            declared_rounds=5,
        )
    )
    third = session.scalars(select(Round).where(Round.number == 3)).one()
    for game in third.games:
        if game.black_rank is not None:
            send(SetResult(game_id=game.id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=third.id))
    send(ExportRound(round_id=third.id))

    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=read("sorted_pairs_round4.txt"),
        )
    )
    fourth = session.scalars(select(Round).where(Round.number == 4)).one()
    boards = {g.board: g for g in fourth.games}
    send(SetResult(game_id=boards[1].id, white_result="=", black_result="="))
    send(ReleaseRound(round_id=fourth.id, force=True))
    exported = send(ExportRound(round_id=fourth.id, force=True))

    ours = parse(exported.content)
    assert ours.rounds_present == 4
    assert ours.declared_rounds == 5
    four = ours.players[4]  # Mueller: + 1 1 from the cross table and round 3, then a draw
    assert {r: (e.opponent, e.result) for r, e in four.rounds.items()} == {
        1: (8, "+"),
        2: (9, "1"),
        3: (2, "1"),
        4: (1, "="),
    }
    assert four.points == 3.5
    assert ours.players[5].rounds[2].result == "H"
    assert ours.players[9].rounds[1].result == "U"
    assert ours.players[8].rounds[4].opponent is None  # the bye Vega gave in round 4
    assert exported.boards_written == 1


def test_a_late_comer_needs_the_cross_table_again(send: Send, tournament: Tournament) -> None:
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=round_three(),
            declared_rounds=5,
        )
    )
    with pytest.raises(ValidationFailed, match="Keller, Simon"):
        send(
            PreviewImport(
                tournament_id=tournament.id,
                section_name="A",
                content=read("sorted_pairs_round4_latecomer.txt"),
            )
        )
    plan = send(
        PreviewImport(
            tournament_id=tournament.id,
            section_name="A",
            content=read("crosstable_latecomer.txt") + read("sorted_pairs_round4_latecomer.txt"),
        )
    )
    assert plan.file_round == 4
    assert [c.name for c in plan.players_added] == ["Keller, Simon"]
    assert plan.byes == 0


def test_a_manual_change_and_accented_names_are_read_from_the_pairing_list() -> None:
    """The engine's own file went stale; the list Vega rewrote carries the change."""
    vega = manager_for("vega")
    document = vega.read_round(
        read("sorted_pairs_round3_manual_accents.txt") + read("crosstable_accents.txt")
    )
    rows = {row.board: row for row in document.board_rows(3)}
    assert (rows[3].white_name, rows[3].black_name) == ("Huber, Marco", "Iten, Nadia")
    assert (rows[4].white_name, rows[4].black_name) == ("Jenni, Rafael", "Fischer, Jonas")
    assert rows[1].white_name == "Müller, Tobias"

    out = vega.write_results(document, 3, [], stem="A")
    line = next(row for row in out.content.split("\r\n") if "Müller" in row)
    # Byte-padded: the rating column sits where an ASCII reader expects it.
    assert line.encode("utf-8")[48:52] == b"2044"


def test_the_first_round_still_needs_both_files(send: Send, tournament: Tournament) -> None:
    with pytest.raises(ValidationFailed) as caught:
        send(
            PreviewImport(
                tournament_id=tournament.id,
                section_name="A",
                content=read("sorted_pairs_round3.txt"),
            )
        )
    assert "engine26.trf" in str(caught.value)

    with pytest.raises(ValidationFailed) as caught:
        send(
            PreviewImport(
                tournament_id=tournament.id,
                section_name="A",
                content=read("crosstable_round2.txt"),
            )
        )
    assert "SortedPairs.txt" in str(caught.value)


def test_a_trf_still_reads_for_a_vega_tournament(round1_text: str) -> None:
    document = manager_for("vega").read_round(round1_text)
    assert document.round_number == 1


def test_the_pairing_list_naming_a_stranger_is_a_readable_error() -> None:
    stranger = read("sorted_pairs_round3.txt").replace("Chen, Wei", "Chan, Wei")
    text = read("crosstable_round2.txt") + "\n" + stranger
    with pytest.raises(InterchangeError, match="Chan, Wei"):
        manager_for("vega").read_round(text)


# --- engine26.trf: the players from round 1 on ------------------------------


def round_one() -> str:
    return read("engine26_round1.trf") + "\n" + read("sorted_pairs_round1.txt")


def test_round_one_comes_in_from_the_engine_file_and_the_pairing_list(
    send: Send, tournament: Tournament
) -> None:
    """A fresh Vega tournament has no crosstable.txt until a result exists;
    engine26.trf is there from the first pairing, round count included."""
    plan = send(PreviewImport(tournament_id=tournament.id, section_name="A", content=round_one()))
    assert plan.tournament_name == "TestOpen"
    assert plan.file_round == 1
    assert plan.declared_rounds == 5  # from the file's 142 line: nobody was asked
    assert plan.boards == 8
    assert plan.byes == 0
    assert len(plan.players_added) == 16


def test_names_take_the_pairing_lists_spelling_not_the_engine_files() -> None:
    document = manager_for("vega").read_round(round_one())
    assert document.players[1].name == "Baumann, Lukas"  # the TRF says BaumannLukas
    assert document.players[3].title == "WFM"
    assert document.players[16].rating is None  # unrated: 0 in the file
    board = document.pairings[1][1]
    assert (board.white_rank, board.black_rank) == (10, 2)
    # The TRF we build for the export leg carries the sex and birth year Vega wrote.
    line = next(ln for ln in document.source.splitlines() if ln.startswith("001    3 "))
    assert " w" in line[8:12] and "2001" in line


def test_the_engine_file_carries_history_with_colours_byes_and_forfeits() -> None:
    text = read("engine26_after_import.trf") + "\n" + read("sorted_pairs_round4.txt")
    document = manager_for("vega").read_round(text)
    assert document.round_number == 4
    assert document.declared_rounds == 5
    assert sorted(document.pairings) == [1, 2, 3, 4]
    by_pair = {(p.white_rank, p.black_rank): p for p in document.pairings[1]}
    assert by_pair[(4, 8)].white_result == "+"  # the forfeit keeps its colour here
    assert by_pair[(9, None)].white_result == "U"
    by_pair = {(p.white_rank, p.black_rank): p for p in document.pairings[2]}
    assert by_pair[(5, None)].white_result == "H"
    assert [p.board for p in document.pairings[4]] == [1, 2, 3, 4, 5]


def test_an_engine_file_that_is_behind_the_pairing_list_is_refused() -> None:
    """engine26.trf is written when the engine pairs; after a manual pairing it
    still describes the round before. Its history would be short one round."""
    text = read("engine26_round1.trf") + "\n" + read("sorted_pairs_round3.txt")
    with pytest.raises(InterchangeError, match=r"crosstable.txt"):
        manager_for("vega").read_round(text)


def test_a_player_the_list_does_not_name_gets_an_unsquashed_name() -> None:
    """Whoever sits the round out is only in the TRF, as ``GruberSarah``."""
    pairs = read("sorted_pairs_round1.txt").replace("Gruber, Sarah", "Peter, Anna")
    pairs = "\n".join(
        ln for ln in pairs.splitlines() if "in board    7" not in ln
    )  # Huber and Peter's board is gone; Peter now plays Oberli's board
    document = manager_for("vega").read_round(read("engine26_round1.trf") + "\n" + pairs)
    assert document.players[6].name == "Gruber, Sarah"
    assert document.players[7].name == "Huber, Marco"


# --- standings.txt ----------------------------------------------------------


def test_vegas_standings_come_in_from_its_standings_file(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """standings.txt from the same 16-player tournament as the round-1 files,
    written by Vega after round 3; matched on the start number."""
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round_one()))
    outcome = send(
        ImportStandings(
            tournament_id=tournament.id, section_name="A", content=read("standings_round3.txt")
        )
    )
    assert outcome.players_updated == 16
    assert outcome.unknown_start_numbers == []
    assert outcome.standings.tiebreak_names == ["Buchholz"]
    rows = {row.start_rank: row for row in outcome.standings.rows}
    assert (rows[6].rank, rows[6].points, rows[6].tiebreaks) == (1, 2.5, [5.0])
    assert (rows[10].rank, rows[10].points) == (1, 2.5)  # shares the position
    assert (rows[13].rank, rows[13].points, rows[13].tiebreaks) == (15, 0.5, [4.5])
    assert outcome.standings.rows[0].start_rank == 6
    assert [row.rank for row in outcome.standings.rows][:4] == [1, 1, 3, 4]


def test_the_wrong_file_on_the_standings_page_names_the_right_one(
    send: Send, tournament: Tournament
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round_one()))
    with pytest.raises(ValidationFailed, match=r"standings.txt"):
        send(
            ImportStandings(
                tournament_id=tournament.id,
                section_name="A",
                content=read("sorted_pairs_round1.txt"),
            )
        )
