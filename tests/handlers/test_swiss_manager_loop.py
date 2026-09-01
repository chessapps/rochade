"""The Swiss-Manager round, end to end, on the files Swiss-Manager actually wrote.

`round3_paired.trf` is what `Extras -> FIDE-Daten-Export TRF16` produced with
round 3 paired and unplayed. `pairings_round4_we_wrote.txt` is a file we
handed back that Swiss-Manager merged and scored. The tests below import the
one, enter results, and assert the export is the other kind of file -- the same
shape, the same codes, the same board numbers as Swiss-Manager's own.
"""

from __future__ import annotations

import pathlib

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.games.claim_result import ClaimResult
from seebach.features.games.set_result import SetResult
from seebach.features.imports.import_round import ImportRound
from seebach.features.imports.preview_import import PreviewImport
from seebach.features.rounds.export_round import ExportRound
from seebach.features.rounds.release_round import ReleaseRound
from seebach.interchange import InterchangeError, ResultEntry, manager_for
from seebach.platform.errors import Conflict
from seebach.shared.enums import GameResult
from seebach.shared.models import Round, Tournament
from seebach.swiss_manager import parse_pairing_file
from tests.conftest import Send
from tests.handlers.test_result_flow import device_of

pytestmark = pytest.mark.db

SM = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "swiss_manager"


def read(name: str) -> str:
    return (SM / name).read_bytes().decode("utf-8")


def test_preview_reads_the_real_export_as_round_3_with_history(
    send: Send, tournament: Tournament
) -> None:
    plan = send(
        PreviewImport(
            tournament_id=tournament.id,
            section_name="A",
            content=read("round3_paired.trf"),
            manager="swiss_manager",
        )
    )
    assert plan.tournament_name == "Seebach M0 Spike"
    assert plan.file_round == 3
    assert plan.declared_rounds == 5  # from Swiss-Manager's `142 5`
    assert plan.boards == 4
    assert plan.byes == 1
    assert len(plan.players_added) == 9


def test_boards_carry_swiss_managers_numbers(
    send: Send, session: Session, tournament: Tournament
) -> None:
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=read("round3_paired.trf"),
            manager="swiss_manager",
        )
    )
    round_ = session.scalars(select(Round).where(Round.number == 3)).one()
    boards = sorted(round_.games, key=lambda g: g.board)
    # Straight off Swiss-Manager's pairing list for round 3.
    assert [(g.board, g.white_rank, g.black_rank) for g in boards] == [
        (1, 4, 2),
        (2, 1, 3),
        (3, 7, 9),
        (4, 5, 8),
        (5, 6, None),
    ]
    assert boards[0].white_name == "Mueller,Tobias"


def test_the_export_is_the_pairing_file_swiss_manager_took(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """Round 4's real export in, the results we really entered, the file we really sent."""
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=read("round4_paired.trf"),
            manager="swiss_manager",
        )
    )
    round_ = session.scalars(select(Round).where(Round.number == 4)).one()
    boards = {g.board: g for g in round_.games}
    phone = device_of(tournament, "a")

    send(ClaimResult(game_id=boards[1].id, result=GameResult.BLACK_WIN), principal=phone)
    send(ClaimResult(game_id=boards[2].id, result=GameResult.DRAW), principal=phone)
    # Nobody turned up on board 3; board 4's white player did not either.
    send(SetResult(game_id=boards[3].id, white_result="-", black_result="-"))
    send(SetResult(game_id=boards[4].id, white_result="-", black_result="+"))
    send(ReleaseRound(round_id=round_.id))

    exported = send(ExportRound(round_id=round_.id))
    assert exported.manager == "swiss_manager"
    assert exported.file_format == "swiss-manager pairing file"
    assert exported.filename == "A-round4.txt"
    assert exported.boards_written == 4
    assert exported.content == read("pairings_round4_we_wrote.txt")


def test_byes_other_than_the_pairing_allocated_one_are_not_rows(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """A half-point bye is a player status in Swiss-Manager, not a pairing."""
    manager = manager_for("swiss_manager")
    document = manager.read_round(read("round3_paired.trf"))
    # Round 2 holds Fischer's H bye; round 3 holds Gruber's U bye.
    round2 = manager.write_results(document, 2, [], stem="x")
    round3 = manager.write_results(document, 3, [], stem="x")
    assert [line.is_bye for line in parse_pairing_file(round2.content)] == [False] * 4
    assert [line.white for line in parse_pairing_file(round3.content) if line.is_bye] == [6]


def test_an_unrated_result_is_refused_before_the_file_is_written(
    send: Send, session: Session, tournament: Tournament
) -> None:
    send(
        ImportRound(
            tournament_id=tournament.id,
            section_name="A",
            content=read("round3_paired.trf"),
            manager="swiss_manager",
        )
    )
    round_ = session.scalars(select(Round).where(Round.number == 3)).one()
    boards = {g.board: g for g in round_.games}
    for board in (2, 3, 4):
        send(SetResult(game_id=boards[board].id, white_result="1", black_result="0"))
    send(SetResult(game_id=boards[1].id, white_result="W", black_result="L"))
    send(ReleaseRound(round_id=round_.id))

    with pytest.raises(Conflict) as refused:
        send(ExportRound(round_id=round_.id))
    assert refused.value.details["codes"] == ["L", "W"]


def test_a_double_forfeit_survives_the_trf_leg_too() -> None:
    """The same `ResultEntry` shape must not hand Vega a `+` nobody earned."""
    vega = manager_for("vega")
    document = vega.read_round(read("round3_paired.trf"))
    out = vega.write_results(
        document, 3, [ResultEntry(white_rank=4, white_result="-", black_result="-")], stem="x"
    )
    row_white = next(line for line in out.content.splitlines() if line.startswith("001    4 "))
    row_black = next(line for line in out.content.splitlines() if line.startswith("001    2 "))
    assert row_white[118] == "-" and row_black[118] == "-"


def test_a_result_for_a_board_the_file_does_not_have_is_refused() -> None:
    manager = manager_for("swiss_manager")
    document = manager.read_round(read("round3_paired.trf"))
    with pytest.raises(InterchangeError, match="have no board"):
        manager.write_results(
            document, 3, [ResultEntry(white_rank=42, white_result="1", black_result="0")], stem="x"
        )


def test_a_dangling_opponent_is_a_readable_error_not_a_crash() -> None:
    # Baumann's round-1 opponent becomes a player the file does not have.
    text = read("round3_paired.trf").replace("    5 w 1     2 b =", "   77 w 1     2 b =")
    with pytest.raises(InterchangeError, match="no such player"):
        manager_for("swiss_manager").read_round(text)
