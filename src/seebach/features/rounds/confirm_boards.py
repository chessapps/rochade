"""The arbiter confirms what the phones entered, board by board or all at once.

Release does this for the whole round at the end; this is the same act
earlier, for the boards the arbiter has already checked against the
scoresheets. A confirmed board is closed to the phones from then on, so a
player's late correction goes to the arbiter instead of overwriting a checked
result. Only CLAIMED boards move: empty and disputed ones still need a
decision, and confirming them blindly is exactly what the release gate forbids.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from seebach.features.audit import record
from seebach.features.locking import lock_round, require_open
from seebach.features.scoping import tournament_of_round
from seebach.platform.bus import bus
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import EventAction, ResultState

router = APIRouter(prefix="/rounds", tags=["arbiter"])


class ConfirmBoardsResult(BaseModel):
    round_id: uuid.UUID
    confirmed: int
    #: Boards asked for that were not CLAIMED, so were left as they were.
    skipped: list[int] = Field(default_factory=list)


class ConfirmBoards(Command):
    access = Access.ARBITER
    result_model = ConfirmBoardsResult

    round_id: uuid.UUID
    #: Empty means every entered board in the round.
    game_ids: list[uuid.UUID] = Field(default_factory=list)
    note: str = Field(default="", max_length=500)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_round(session, self.round_id)


@bus.register(ConfirmBoards)
def handle(command: ConfirmBoards, ctx: Context) -> ConfirmBoardsResult:
    round_ = lock_round(ctx, command.round_id)
    require_open(round_, arbiter=True)

    wanted = set(command.game_ids)
    games = [g for g in round_.games if not wanted or g.id in wanted]

    confirmed = 0
    skipped: list[int] = []
    for game in sorted(games, key=lambda g: g.board):
        if game.state is not ResultState.CLAIMED:
            if wanted:
                skipped.append(game.board)
            continue
        game.state = ResultState.CONFIRMED
        confirmed += 1
        record(
            ctx,
            section_id=round_.section_id,
            round_number=round_.number,
            action=EventAction.RESULT_CONFIRMED,
            game=game,
            board=game.board,
            white_result=game.white_result,
            black_result=game.black_result,
            note=command.note,
        )

    return ConfirmBoardsResult(round_id=round_.id, confirmed=confirmed, skipped=skipped)


class ConfirmBody(BaseModel):
    game_ids: list[uuid.UUID] = Field(default_factory=list)
    note: str = ""


@router.post("/{round_id}/confirm", response_model=ConfirmBoardsResult)
def confirm_boards(
    round_id: uuid.UUID, body: ConfirmBody, ctx: Context = Depends(get_context)
) -> ConfirmBoardsResult:
    result: ConfirmBoardsResult = bus.send(
        ConfirmBoards(round_id=round_id, **body.model_dump()), ctx
    )
    return result
