"""Settle a board where two players entered different results.

Distinct from `set_result` on purpose. Mechanically it is the same write, but
it is a different event in the audit log, and "how many disputes did this
tournament have" is a question worth being able to answer.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from seebach.commands.audit import record
from seebach.commands.locking import lock_round_of_game, require_open
from seebach.commands.scoping import tournament_of_game
from seebach.platform.bus import bus
from seebach.platform.errors import Conflict
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import TRF_CODES, EventAction, GameResult, ResultState

router = APIRouter(prefix="/games", tags=["arbiter"])


class ResolveDisputeResult(BaseModel):
    game_id: uuid.UUID
    state: ResultState
    white_result: str
    black_result: str


class ResolveDispute(Command):
    access = Access.ARBITER
    result_model = ResolveDisputeResult

    game_id: uuid.UUID
    result: GameResult
    note: str = Field(default="", max_length=500)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_game(session, self.game_id)


@bus.register(ResolveDispute)
def handle(command: ResolveDispute, ctx: Context) -> ResolveDisputeResult:
    round_, game = lock_round_of_game(ctx, command.game_id)
    require_open(round_)

    if game.state is not ResultState.DISPUTED:
        raise Conflict(
            "this board is not disputed",
            game_id=str(game.id),
            state=game.state.value,
        )

    contested = {game.white_result, game.disputed_white_result}
    game.white_result, game.black_result = TRF_CODES[command.result]
    game.state = ResultState.CONFIRMED
    game.disputed_white_result = None

    record(
        ctx,
        section_id=round_.section_id,
        round_number=round_.number,
        action=EventAction.DISPUTE_RESOLVED,
        game=game,
        board=game.board,
        contested=sorted(c for c in contested if c),
        chosen=command.result.value,
        note=command.note,
    )

    return ResolveDisputeResult(
        game_id=game.id,
        state=game.state,
        white_result=game.white_result,
        black_result=game.black_result,
    )


class ResolveBody(BaseModel):
    result: GameResult
    note: str = ""


@router.post("/{game_id}/resolve", response_model=ResolveDisputeResult)
def resolve_dispute(
    game_id: uuid.UUID, body: ResolveBody, ctx: Context = Depends(get_context)
) -> ResolveDisputeResult:
    result: ResolveDisputeResult = bus.send(
        ResolveDispute(game_id=game_id, **body.model_dump()), ctx
    )
    return result
