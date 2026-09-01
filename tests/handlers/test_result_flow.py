"""The result state machine, exercised through the mediator.

The legal transitions are enumerated in `test_only_these_transitions_are_legal`
rather than encoded in a shared helper -- a module that owned them would
accrete every rule in the system, whereas a table in a test cannot be forgotten
by a command and cannot be called by one either.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.games.claim_result import ClaimResult
from seebach.features.games.resolve_dispute import ResolveDispute
from seebach.features.games.set_result import SetResult
from seebach.features.imports.import_round import ImportRound
from seebach.features.rounds.release_round import ReleaseRound
from seebach.platform.errors import Conflict, Forbidden, RoundFrozen, ValidationFailed
from seebach.platform.mediator import Principal
from seebach.shared.enums import EventAction, GameResult, PrincipalKind, ResultState, RoundState
from seebach.shared.models import Game, GameEvent, Round, Tournament
from tests.conftest import ARBITER, Send

pytestmark = pytest.mark.db


@pytest.fixture
def round_(send: Send, session: Session, tournament: Tournament, round1_text: str) -> Round:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    return session.scalars(select(Round)).one()


@pytest.fixture
def board(round_: Round) -> Game:
    return sorted(round_.games, key=lambda g: g.board)[0]


def device_of(tournament: Tournament, name: str = "phone-1") -> Principal:
    return Principal(
        kind=PrincipalKind.DEVICE,
        subject=f"device:{name}",
        device_id=uuid.uuid4(),
        tournament_id=tournament.id,
    )


# --- claiming ---------------------------------------------------------------


def test_a_device_can_claim_a_result(
    send: Send, session: Session, tournament: Tournament, board: Game
) -> None:
    result = send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament),
    )
    assert result.state is ResultState.CLAIMED
    assert (result.white_result, result.black_result) == ("1", "0")

    session.refresh(board)
    assert board.state is ResultState.CLAIMED


def test_the_same_claim_twice_is_a_no_op(
    send: Send, session: Session, tournament: Tournament, board: Game
) -> None:
    phone = device_of(tournament)
    send(ClaimResult(game_id=board.id, result=GameResult.DRAW), principal=phone)
    again = send(ClaimResult(game_id=board.id, result=GameResult.DRAW), principal=phone)

    assert again.state is ResultState.CLAIMED
    assert not again.disputed
    session.refresh(board)
    assert board.white_result == "="


def test_a_conflicting_claim_disputes_the_board(
    send: Send, session: Session, tournament: Tournament, board: Game
) -> None:
    send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament, "phone-1"),
    )
    second = send(
        ClaimResult(game_id=board.id, result=GameResult.BLACK_WIN),
        principal=device_of(tournament, "phone-2"),
    )

    assert second.disputed
    session.refresh(board)
    assert board.state is ResultState.DISPUTED
    # The first answer stands until an arbiter chooses; the second is kept
    # alongside it so they can see both sides.
    assert board.white_result == "1"
    assert board.disputed_white_result == "0"

    actions = [e.action for e in session.scalars(select(GameEvent)).all()]
    assert EventAction.RESULT_DISPUTED in actions


def test_a_device_from_another_tournament_is_refused(
    send: Send, tournament: Tournament, board: Game
) -> None:
    intruder = Principal(
        kind=PrincipalKind.DEVICE,
        subject="device:elsewhere",
        device_id=uuid.uuid4(),
        tournament_id=uuid.uuid4(),
    )
    with pytest.raises(Forbidden, match="not admitted"):
        send(ClaimResult(game_id=board.id, result=GameResult.DRAW), principal=intruder)


def test_a_bye_cannot_be_claimed(
    send: Send, session: Session, tournament: Tournament, round3_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round3_text))
    round3 = session.scalars(select(Round).where(Round.number == 3)).one()
    bye = next(g for g in round3.games if g.black_rank is None)

    with pytest.raises(Conflict, match="bye"):
        send(
            ClaimResult(game_id=bye.id, result=GameResult.WHITE_WIN),
            principal=device_of(tournament),
        )


def test_an_offline_retry_cannot_double_submit(
    send: Send, session: Session, tournament: Tournament, board: Game
) -> None:
    phone = device_of(tournament)
    first = send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=phone,
        idempotency_key="claim-abc",
    )
    replay = send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=phone,
        idempotency_key="claim-abc",
    )
    assert replay.game_id == first.game_id
    assert replay.state is ResultState.CLAIMED

    claims = [
        e
        for e in session.scalars(select(GameEvent)).all()
        if e.action is EventAction.RESULT_CLAIMED
    ]
    assert len(claims) == 1


# --- arbiter overrides ------------------------------------------------------


def test_the_arbiter_can_set_a_forfeit(send: Send, session: Session, board: Game) -> None:
    result = send(SetResult(game_id=board.id, white_result="+", black_result="-"))
    assert result.state is ResultState.CONFIRMED
    session.refresh(board)
    assert (board.white_result, board.black_result) == ("+", "-")


def test_a_double_forfeit_has_no_single_code_form(
    send: Send, session: Session, board: Game
) -> None:
    send(SetResult(game_id=board.id, white_result="-", black_result="-"))
    session.refresh(board)
    assert (board.white_result, board.black_result) == ("-", "-")


def test_an_unknown_code_is_rejected(send: Send, board: Game) -> None:
    with pytest.raises(ValueError, match="unknown TRF result code"):
        send(SetResult(game_id=board.id, white_result="X"))


def test_a_bye_only_accepts_unplayed_codes(
    send: Send, session: Session, tournament: Tournament, round3_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round3_text))
    round3 = session.scalars(select(Round).where(Round.number == 3)).one()
    bye = next(g for g in round3.games if g.black_rank is None)

    with pytest.raises(ValidationFailed, match="unplayed-game code"):
        send(SetResult(game_id=bye.id, white_result="1"))

    send(SetResult(game_id=bye.id, white_result="H"))
    session.refresh(bye)
    assert bye.white_result == "H"


def test_the_arbiter_overrides_a_claim(
    send: Send, session: Session, tournament: Tournament, board: Game
) -> None:
    send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament),
    )
    send(SetResult(game_id=board.id, white_result="0", black_result="1", note="scoresheet"))
    session.refresh(board)
    assert board.state is ResultState.CONFIRMED
    assert board.white_result == "0"


def test_a_device_cannot_set_a_result(send: Send, tournament: Tournament, board: Game) -> None:
    with pytest.raises(Forbidden):
        send(
            SetResult(game_id=board.id, white_result="+"),
            principal=device_of(tournament),
        )


# --- disputes ---------------------------------------------------------------


def test_resolving_a_dispute(
    send: Send, session: Session, tournament: Tournament, board: Game
) -> None:
    send(
        ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
        principal=device_of(tournament, "a"),
    )
    send(
        ClaimResult(game_id=board.id, result=GameResult.BLACK_WIN),
        principal=device_of(tournament, "b"),
    )
    send(ResolveDispute(game_id=board.id, result=GameResult.DRAW, note="both agreed"))

    session.refresh(board)
    assert board.state is ResultState.CONFIRMED
    assert (board.white_result, board.black_result) == ("=", "=")
    assert board.disputed_white_result is None

    event = session.scalars(
        select(GameEvent).where(GameEvent.action == EventAction.DISPUTE_RESOLVED)
    ).one()
    assert sorted(event.payload["contested"]) == ["0", "1"]


def test_resolving_an_undisputed_board_is_refused(send: Send, board: Game) -> None:
    with pytest.raises(Conflict, match="not disputed"):
        send(ResolveDispute(game_id=board.id, result=GameResult.DRAW))


# --- release ----------------------------------------------------------------


def _claim_all(send: Send, tournament: Tournament, round_: Round) -> None:
    phone = device_of(tournament)
    for game in round_.games:
        if game.black_rank is not None:
            send(ClaimResult(game_id=game.id, result=GameResult.WHITE_WIN), principal=phone)


def test_release_confirms_every_claim(
    send: Send, session: Session, tournament: Tournament, round_: Round
) -> None:
    _claim_all(send, tournament, round_)
    result = send(ReleaseRound(round_id=round_.id))

    assert result.confirmed == 4
    session.refresh(round_)
    assert round_.state is RoundState.CONFIRMED
    assert round_.released_at is not None
    assert all(g.state is ResultState.CONFIRMED for g in round_.games)


def test_release_is_blocked_by_empty_boards(send: Send, round_: Round) -> None:
    with pytest.raises(Conflict) as excinfo:
        send(ReleaseRound(round_id=round_.id))
    assert excinfo.value.details["empty_boards"] == [1, 2, 3, 4]


def test_release_is_blocked_by_a_dispute(
    send: Send, tournament: Tournament, round_: Round, board: Game
) -> None:
    _claim_all(send, tournament, round_)
    send(
        ClaimResult(game_id=board.id, result=GameResult.BLACK_WIN),
        principal=device_of(tournament, "other"),
    )
    with pytest.raises(Conflict) as excinfo:
        send(ReleaseRound(round_id=round_.id))
    assert excinfo.value.details["disputed_boards"] == [board.board]


def test_release_can_be_forced_and_is_logged_as_such(
    send: Send, session: Session, round_: Round
) -> None:
    result = send(ReleaseRound(round_id=round_.id, force=True, note="paper scoresheets"))
    assert result.forced
    event = session.scalars(
        select(GameEvent).where(GameEvent.action == EventAction.ROUND_RELEASED)
    ).one()
    assert event.payload["forced"] is True
    assert event.payload["empty_boards"] == [1, 2, 3, 4]


def test_a_released_round_stops_accepting_entries(
    send: Send, tournament: Tournament, round_: Round, board: Game
) -> None:
    _claim_all(send, tournament, round_)
    send(ReleaseRound(round_id=round_.id))
    with pytest.raises(RoundFrozen, match="released"):
        send(
            ClaimResult(game_id=board.id, result=GameResult.DRAW),
            principal=device_of(tournament),
        )


def test_a_round_cannot_be_released_twice(
    send: Send, tournament: Tournament, round_: Round
) -> None:
    _claim_all(send, tournament, round_)
    send(ReleaseRound(round_id=round_.id))
    with pytest.raises(Conflict, match="already been released"):
        send(ReleaseRound(round_id=round_.id))


# --- the state machine, enumerated ------------------------------------------

LEGAL_TRANSITIONS = [
    (ResultState.EMPTY, "claim", ResultState.CLAIMED),
    (ResultState.EMPTY, "set", ResultState.CONFIRMED),
    (ResultState.CLAIMED, "claim_same", ResultState.CLAIMED),
    (ResultState.CLAIMED, "claim_different", ResultState.DISPUTED),
    (ResultState.CLAIMED, "set", ResultState.CONFIRMED),
    (ResultState.CLAIMED, "release", ResultState.CONFIRMED),
    (ResultState.DISPUTED, "resolve", ResultState.CONFIRMED),
    (ResultState.DISPUTED, "set", ResultState.CONFIRMED),
]


@pytest.mark.parametrize(("start", "action", "expected"), LEGAL_TRANSITIONS)
def test_only_these_transitions_are_legal(
    send: Send,
    session: Session,
    tournament: Tournament,
    round_: Round,
    start: ResultState,
    action: str,
    expected: ResultState,
) -> None:
    game = sorted(round_.games, key=lambda g: g.board)[0]
    phone = device_of(tournament, "a")
    other = device_of(tournament, "b")

    if start in (ResultState.CLAIMED, ResultState.DISPUTED):
        send(ClaimResult(game_id=game.id, result=GameResult.WHITE_WIN), principal=phone)
    if start is ResultState.DISPUTED:
        send(ClaimResult(game_id=game.id, result=GameResult.BLACK_WIN), principal=other)

    session.refresh(game)
    assert game.state is start

    if action == "claim":
        send(ClaimResult(game_id=game.id, result=GameResult.WHITE_WIN), principal=phone)
    elif action == "claim_same":
        send(ClaimResult(game_id=game.id, result=GameResult.WHITE_WIN), principal=other)
    elif action == "claim_different":
        send(ClaimResult(game_id=game.id, result=GameResult.DRAW), principal=other)
    elif action == "set":
        send(SetResult(game_id=game.id, white_result="=", black_result="="))
    elif action == "resolve":
        send(ResolveDispute(game_id=game.id, result=GameResult.DRAW))
    elif action == "release":
        for other_game in round_.games:
            if other_game.id != game.id:
                send(SetResult(game_id=other_game.id, white_result="=", black_result="="))
        send(ReleaseRound(round_id=round_.id))

    session.refresh(game)
    assert game.state is expected


def test_a_confirmed_board_refuses_further_claims(
    send: Send, tournament: Tournament, board: Game
) -> None:
    send(SetResult(game_id=board.id, white_result="=", black_result="="))
    with pytest.raises(Conflict, match="already confirmed"):
        send(
            ClaimResult(game_id=board.id, result=GameResult.WHITE_WIN),
            principal=device_of(tournament),
        )


def test_an_assistant_cannot_release(send: Send, round_: Round) -> None:
    stranger = Principal(kind=PrincipalKind.STAFF, subject="nobody@example.test")
    with pytest.raises(Forbidden):
        send(ReleaseRound(round_id=round_.id), principal=stranger)
    assert ARBITER.subject != stranger.subject
