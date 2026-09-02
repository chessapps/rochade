"""The full Vega round trip, in one test.

Import round 1 -> players claim -> a dispute -> resolve -> release -> export,
then assert the exported TRF parses, carries exactly the confirmed results, and
differs from the imported file in nothing but the cells we own.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.games.claim_result import ClaimResult
from seebach.features.games.resolve_dispute import ResolveDispute
from seebach.features.games.set_result import SetResult
from seebach.features.imports.import_round import ImportRound
from seebach.features.rounds.export_round import ExportRound, GetExportFile
from seebach.features.rounds.release_round import ReleaseRound
from seebach.platform.errors import Conflict, RoundFrozen
from seebach.shared.enums import GameResult, ResultState, RoundState
from seebach.shared.models import Game, Round, Tournament
from seebach.trf import Dialect, parse, serialize
from tests.conftest import Send
from tests.handlers.test_result_flow import device_of

pytestmark = pytest.mark.db


def test_the_loop_closes(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    boards = sorted(round_.games, key=lambda g: g.board)
    phone_a, phone_b = device_of(tournament, "a"), device_of(tournament, "b")

    send(ClaimResult(game_id=boards[0].id, result=GameResult.WHITE_WIN), principal=phone_a)
    send(ClaimResult(game_id=boards[1].id, result=GameResult.DRAW), principal=phone_a)
    send(ClaimResult(game_id=boards[2].id, result=GameResult.BLACK_WIN), principal=phone_a)

    # Board 4 goes wrong: two phones disagree, so the arbiter settles it.
    send(ClaimResult(game_id=boards[3].id, result=GameResult.WHITE_WIN), principal=phone_a)
    send(ClaimResult(game_id=boards[3].id, result=GameResult.BLACK_WIN), principal=phone_b)
    session.refresh(boards[3])
    assert boards[3].state is ResultState.DISPUTED
    send(ResolveDispute(game_id=boards[3].id, result=GameResult.DRAW))

    send(ReleaseRound(round_id=round_.id))
    exported = send(ExportRound(round_id=round_.id))

    assert exported.boards_written == 4
    assert exported.boards_left_blank == []
    assert exported.filename == "A-round1.trf"

    out = parse(exported.content)
    # Boards are (1,5) (6,2) (3,7) (8,4) in FIDE order.
    assert out.player(1).round(1).result == "1"
    assert out.player(5).round(1).result == "0"
    assert out.player(6).round(1).result == "="
    assert out.player(2).round(1).result == "="
    assert out.player(3).round(1).result == "0"
    assert out.player(7).round(1).result == "1"
    assert out.player(8).round(1).result == "="
    assert out.player(4).round(1).result == "="

    # Points moved with the results, so the file is internally consistent.
    assert out.player(1).points == 1.0
    assert out.player(6).points == 0.5
    assert out.player(7).points == 1.0

    session.refresh(round_)
    assert round_.state is RoundState.EXPORTED
    assert round_.exported_at is not None


def test_export_touches_only_the_result_and_points_cells(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    for game in round_.games:
        send(SetResult(game_id=game.id, white_result="=", black_result="="))
    send(ReleaseRound(round_id=round_.id))
    exported = send(ExportRound(round_id=round_.id))

    before = round1_text.split("\r\n")
    after = exported.content.split("\r\n")
    assert len(before) == len(after)

    from seebach.trf import columns

    allowed = set(range(columns.POINTS.start, columns.POINTS.stop))
    allowed.add(columns.result_index(1))
    for a, b in zip(before, after, strict=True):
        differing = {i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y}
        assert differing <= allowed


def test_export_is_refused_before_release(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    with pytest.raises(Conflict, match="not released this round"):
        send(ExportRound(round_id=round_.id))


def test_a_forced_export_reports_the_boards_it_left_blank(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    board = sorted(round_.games, key=lambda g: g.board)[0]
    send(SetResult(game_id=board.id, white_result="1", black_result="0"))

    exported = send(ExportRound(round_id=round_.id, force=True))
    assert exported.forced
    assert exported.boards_written == 1
    assert exported.boards_left_blank == [2, 3, 4]

    out = parse(exported.content)
    assert out.player(3).round(1).result == " "


def test_an_exported_round_is_frozen(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    board = sorted(round_.games, key=lambda g: g.board)[0]
    for game in round_.games:
        send(SetResult(game_id=game.id, white_result="=", black_result="="))
    send(ReleaseRound(round_id=round_.id))
    send(ExportRound(round_id=round_.id))

    with pytest.raises(RoundFrozen, match="read-only"):
        send(SetResult(game_id=board.id, white_result="1", black_result="0"))
    with pytest.raises(RoundFrozen, match="read-only"):
        send(
            ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
            principal=device_of(tournament),
        )
    with pytest.raises(Conflict, match="already been exported"):
        send(ExportRound(round_id=round_.id))


def test_byes_are_written_back_unchanged(
    send: Send, session: Session, tournament: Tournament, round3_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round3_text))
    round3 = session.scalars(select(Round).where(Round.number == 3)).one()
    for game in round3.games:
        if game.black_rank is not None:
            send(SetResult(game_id=game.id, white_result="=", black_result="="))
    send(ReleaseRound(round_id=round3.id))
    exported = send(ExportRound(round_id=round3.id))

    out = parse(exported.content)
    # Player 9 withdrew: their zero-point bye must survive with the same code.
    assert out.player(9).round(3).result == "Z"
    assert out.player(9).round(3).opponent is None
    # And the earlier rounds are untouched, forfeit codes included.
    assert out.player(5).round(2).result == "+"
    assert out.player(7).round(2).result == "-"
    assert out.player(4).round(1).result == "H"


def test_the_export_round_trips_through_the_parser(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    for game in round_.games:
        send(SetResult(game_id=game.id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=round_.id))
    exported = send(ExportRound(round_id=round_.id))

    assert serialize(parse(exported.content), Dialect.TRF16) == exported.content


def test_the_next_round_can_be_imported_after_export(
    send: Send, session: Session, tournament: Tournament, round1_text: str, round3_text: str
) -> None:
    """The loop continues: export round 1, then take Vega's next file."""
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round1 = session.scalars(select(Round)).one()
    for game in round1.games:
        send(SetResult(game_id=game.id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=round1.id))
    send(ExportRound(round_id=round1.id))

    two_rounds = _truncate_to_round(round3_text, 2)
    result = send(ImportRound(tournament_id=tournament.id, section_name="A", content=two_rounds))
    assert result.round_number == 2

    rounds = session.scalars(select(Round).order_by(Round.number)).all()
    assert [r.state for r in rounds] == [RoundState.EXPORTED, RoundState.OPEN]
    # Vega is authoritative: round 1 now carries the results the file states,
    # not the ones we had exported.
    round1_games = {(g.white_rank, g.black_rank): g for g in rounds[0].games}
    assert round1_games[(1, 5)].white_result == "1"
    assert round1_games[(3, 7)].white_result == "="


def _truncate_to_round(text: str, last_round: int) -> str:
    """Cut a TRF back to its first `last_round` rounds."""
    from seebach.trf import columns

    lines = []
    for line in text.split("\r\n"):
        if line.startswith("001"):
            line = line[: columns.round_base(last_round + 1)].rstrip()
        lines.append(line)
    return "\r\n".join(lines)


def test_a_game_row_keeps_both_sides_of_a_bye_null(
    send: Send, session: Session, tournament: Tournament, round3_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round3_text))
    byes = session.scalars(select(Game).where(Game.black_rank.is_(None))).all()
    assert byes
    assert all(g.black_name is None for g in byes)


def test_the_exported_file_can_be_downloaded_again(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()

    # Not before the export: there is no file yet to hand back.
    with pytest.raises(Conflict):
        send(GetExportFile(round_id=round_.id))

    phone = device_of(tournament)
    for game in round_.games:
        if game.black_rank is not None:
            send(ClaimResult(game_id=game.id, result=GameResult.DRAW), principal=phone)
    send(ReleaseRound(round_id=round_.id))
    exported = send(ExportRound(round_id=round_.id))

    again = send(GetExportFile(round_id=round_.id))
    assert again.content == exported.content
    assert again.filename == exported.filename
    assert again.next_step == exported.next_step
    assert again.forced is False


def test_a_forced_export_downloads_again_with_the_same_blanks(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    boards = sorted(round_.games, key=lambda g: g.board)
    send(SetResult(game_id=boards[0].id, white_result="1", black_result="0"))
    send(ReleaseRound(round_id=round_.id, force=True))
    exported = send(ExportRound(round_id=round_.id, force=True))

    again = send(GetExportFile(round_id=round_.id))
    assert again.content == exported.content
    assert again.boards_left_blank == exported.boards_left_blank
    assert again.forced is True
