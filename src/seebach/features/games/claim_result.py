"""A player enters the result of their own board, from a phone in the hall.

Provisional by construction. A claim is never final until the arbiter releases
the round, which is what makes it safe to let an anonymous device write at all.

A second, different claim on the same board does not overwrite the first: it
flips the board to DISPUTED and pushes it to the arbiter's queue. A second
identical claim is a no-op, because that is what an offline retry looks like.

The one exception is the phone that made the standing claim changing its own
mind: that is a correction, not a dispute, and replaces the claim outright.
The arbiter should not have to settle an argument a player had with their
own thumb.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.audit import record
from seebach.features.locking import lock_round_of_game, require_open
from seebach.features.scoping import tournament_of_game
from seebach.platform.bus import bus
from seebach.platform.errors import Conflict
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import TRF_CODES, EventAction, GameResult, ResultState
from seebach.shared.models import Game, GameEvent, Round

router = APIRouter(prefix="/games", tags=["hall"])


class ClaimResultResult(BaseModel):
    game_id: uuid.UUID
    state: ResultState
    white_result: str
    black_result: str
    disputed: bool


class ClaimResult(Command):
    access = Access.DEVICE
    result_model = ClaimResultResult

    game_id: uuid.UUID
    result: GameResult

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_game(session, self.game_id)


@bus.register(ClaimResult)
def handle(command: ClaimResult, ctx: Context) -> ClaimResultResult:
    round_, game = lock_round_of_game(ctx, command.game_id)
    require_open(round_)

    if game.black_rank is None:
        raise Conflict(
            "this board is a bye -- there is no game to report",
            game_id=str(game.id),
        )

    white_code, black_code = TRF_CODES[command.result]

    if game.state is ResultState.CONFIRMED:
        raise Conflict(
            "the arbiter has already confirmed this board; ask them to change it",
            game_id=str(game.id),
        )

    if game.state is ResultState.EMPTY:
        game.white_result, game.black_result = white_code, black_code
        game.state = ResultState.CLAIMED
        action = EventAction.RESULT_CLAIMED
    elif game.white_result == white_code:
        # Same answer again -- a retry from the offline queue, or the opponent
        # confirming what was already entered. Nothing to change.
        action = EventAction.RESULT_CLAIMED
    elif game.state is ResultState.CLAIMED and _claimed_by(ctx, round_, game) == (
        ctx.principal.device_id
    ):
        game.white_result, game.black_result = white_code, black_code
        action = EventAction.RESULT_CORRECTED
    else:
        game.disputed_white_result = white_code
        game.state = ResultState.DISPUTED
        action = EventAction.RESULT_DISPUTED

    record(
        ctx,
        section_id=round_.section_id,
        round_number=round_.number,
        action=action,
        game=game,
        board=game.board,
        claimed=command.result.value,
        standing=game.white_result,
        state=game.state.value,
    )

    return ClaimResultResult(
        game_id=game.id,
        state=game.state,
        white_result=game.white_result,
        black_result=game.black_result,
        disputed=game.state is ResultState.DISPUTED,
    )


def _claimed_by(ctx: Context, round_: Round, game: Game) -> uuid.UUID | None:
    """The device behind the claim that currently stands on this board."""
    return ctx.session.scalar(
        select(GameEvent.device_id)
        .where(
            GameEvent.section_id == round_.section_id,
            GameEvent.round_number == round_.number,
            GameEvent.white_name == game.white_name,
            GameEvent.black_name == game.black_name,
            GameEvent.action.in_([EventAction.RESULT_CLAIMED, EventAction.RESULT_CORRECTED]),
        )
        .order_by(GameEvent.created_at.desc(), GameEvent.id.desc())
        .limit(1)
    )


class ClaimBody(BaseModel):
    result: GameResult


@router.post("/{game_id}/claim", response_model=ClaimResultResult)
def claim_result(
    game_id: uuid.UUID, body: ClaimBody, ctx: Context = Depends(get_context)
) -> ClaimResultResult:
    result: ClaimResultResult = bus.send(ClaimResult(game_id=game_id, result=body.result), ctx)
    return result
