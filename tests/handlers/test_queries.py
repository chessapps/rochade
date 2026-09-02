from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.boards.get_board_list import GetBoardList
from seebach.features.games.claim_result import ClaimResult
from seebach.features.games.set_result import SetResult
from seebach.features.imports.import_round import ImportRound
from seebach.features.queue.get_arbiter_queue import GetArbiterQueue
from seebach.features.rounds.get_round import GetRound
from seebach.features.rounds.release_round import ReleaseRound
from seebach.features.tournaments.create_tournament import CreateTournament
from seebach.features.tournaments.get_tournament import GetTournament
from seebach.features.tournaments.list_tournaments import ListTournaments
from seebach.platform.errors import Forbidden, NotFound, ValidationFailed
from seebach.shared.enums import GameResult, ResultState, Role, RoundState
from seebach.shared.models import Round, Tournament
from tests.conftest import ARBITER, OWNER, Send
from tests.handlers.test_result_flow import device_of

pytestmark = pytest.mark.db


def test_creating_a_tournament_makes_the_creator_its_owner(send: Send) -> None:
    created = send(CreateTournament(name="Club Championship", city="Zurich"))
    listed = send(ListTournaments())
    assert [t.id for t in listed] == [created.id]
    assert listed[0].role is Role.OWNER


def test_a_tournament_you_are_not_a_member_of_is_not_listed(
    send: Send, tournament: Tournament
) -> None:
    from seebach.platform.mediator import Principal
    from seebach.shared.enums import PrincipalKind

    stranger = Principal(kind=PrincipalKind.STAFF, subject="stranger@example.test")
    assert send(ListTournaments(), principal=stranger) == []
    with pytest.raises(Forbidden):
        send(GetTournament(tournament_id=tournament.id), principal=stranger)


def test_a_tournament_that_ends_before_it_starts_is_rejected(send: Send) -> None:
    import datetime

    with pytest.raises(ValidationFailed, match="ends before it starts"):
        send(
            CreateTournament(
                name="Impossible",
                start_date=datetime.date(2026, 5, 2),
                end_date=datetime.date(2026, 5, 1),
            )
        )


def test_tournament_detail_counts_boards_by_state(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    boards = sorted(round_.games, key=lambda g: g.board)
    send(
        ClaimResult(game_id=boards[0].id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament),
    )
    send(SetResult(game_id=boards[1].id, white_result="=", black_result="="))

    detail = send(GetTournament(tournament_id=tournament.id))
    assert len(detail.sections) == 1
    section = detail.sections[0]
    assert section.players == 8
    assert section.declared_rounds == 5

    summary = section.rounds[0]
    assert summary.boards == 4
    assert (summary.empty, summary.claimed, summary.confirmed) == (2, 1, 1)
    assert not summary.ready_to_release


def test_unknown_ids_are_not_found(send: Send) -> None:
    with pytest.raises((NotFound, Forbidden)):
        send(GetTournament(tournament_id=uuid.uuid4()))
    with pytest.raises((NotFound, Forbidden)):
        send(GetRound(round_id=uuid.uuid4()))


def test_the_round_view_shows_every_board(
    send: Send, session: Session, tournament: Tournament, round3_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round3_text))
    round3 = session.scalars(select(Round).where(Round.number == 3)).one()

    detail = send(GetRound(round_id=round3.id))
    assert detail.number == 3
    assert detail.state is RoundState.OPEN
    assert detail.section_name == "A"
    assert len(detail.boards) == 5
    assert sum(1 for b in detail.boards if b.is_bye) == 1


# --- the hall board list ----------------------------------------------------


def test_the_hall_list_spans_every_section(
    send: Send, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    send(ImportRound(tournament_id=tournament.id, section_name="B", content=round1_text))

    listing = send(GetBoardList(tournament_id=tournament.id), principal=device_of(tournament))
    assert len(listing.boards) == 8
    assert {b.section_name for b in listing.boards} == {"A", "B"}
    assert listing.open_rounds == [1]


def test_the_hall_list_can_be_searched_by_either_player(
    send: Send, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    phone = device_of(tournament)

    by_white = send(GetBoardList(tournament_id=tournament.id, q="baumann"), principal=phone)
    assert [b.white_name for b in by_white.boards] == ["Baumann, Lukas"]

    by_black = send(GetBoardList(tournament_id=tournament.id, q="fischer"), principal=phone)
    assert [b.black_name for b in by_black.boards] == ["Fischer, Jonas"]


def test_the_hall_list_marks_entered_boards(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    board = sorted(round_.games, key=lambda g: g.board)[0]
    phone = device_of(tournament)
    send(ClaimResult(game_id=board.id, result=GameResult.DRAW), principal=phone)

    listing = send(GetBoardList(tournament_id=tournament.id), principal=phone)
    entered = [b for b in listing.boards if b.entered]
    assert [b.board for b in entered] == [board.board]
    assert entered[0].state is ResultState.CLAIMED


def test_a_released_round_leaves_the_hall_list(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    for game in round_.games:
        send(SetResult(game_id=game.id, white_result="=", black_result="="))
    send(ReleaseRound(round_id=round_.id))

    listing = send(GetBoardList(tournament_id=tournament.id), principal=device_of(tournament))
    assert listing.boards == []


# --- the arbiter queue ------------------------------------------------------


def test_the_queue_puts_disputes_first(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    round_ = session.scalars(select(Round)).one()
    boards = sorted(round_.games, key=lambda g: g.board)
    a, b = device_of(tournament, "a"), device_of(tournament, "b")

    send(ClaimResult(game_id=boards[0].id, result=GameResult.WHITE_WIN), principal=a)
    send(ClaimResult(game_id=boards[1].id, result=GameResult.WHITE_WIN), principal=a)
    send(ClaimResult(game_id=boards[1].id, result=GameResult.BLACK_WIN), principal=b)
    send(SetResult(game_id=boards[2].id, white_result="=", black_result="="))

    queue = send(GetArbiterQueue(tournament_id=tournament.id))
    assert (queue.disputed, queue.claimed, queue.empty, queue.confirmed) == (1, 1, 1, 1)
    assert queue.blocking == 2
    # Confirmed boards are not work, so they are left out by default.
    assert [e.state for e in queue.entries] == [
        ResultState.DISPUTED,
        ResultState.EMPTY,
        ResultState.CLAIMED,
    ]
    assert queue.entries[0].disputed_white_result == "0"

    with_confirmed = send(GetArbiterQueue(tournament_id=tournament.id, include_confirmed=True))
    assert len(with_confirmed.entries) == 4


def test_an_owner_can_read_the_queue_too(send: Send, tournament: Tournament) -> None:
    queue = send(GetArbiterQueue(tournament_id=tournament.id), principal=OWNER)
    assert queue.entries == []
    assert ARBITER.subject != OWNER.subject


def test_byes_are_counted_apart_from_boards(
    send: Send, tournament: Tournament, round3_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round3_text))
    detail = send(GetTournament(tournament_id=tournament.id))
    rounds = {r.number: r for r in detail.sections[0].rounds}

    # Round 1 had three players sitting out. They are not boards, and nobody
    # enters them, so no progress figure should ever count them.
    assert rounds[1].byes == 3
    assert rounds[1].boards + rounds[1].byes == 6
    assert rounds[1].confirmed == rounds[1].boards
