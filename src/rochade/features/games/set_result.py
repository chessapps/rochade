"""The arbiter writes a result directly.

This is the escape hatch that makes the whole trust model workable: anything a
phone cannot express -- a forfeit because nobody turned up, a correction, a
board neither player entered -- an arbiter can. Whatever they set is CONFIRMED
immediately, because they are the authority the release gate exists to defer to.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.locking import lock_round_of_game, require_open
from rochade.features.scoping import tournament_of_game
from rochade.platform.bus import bus
from rochade.platform.errors import ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction, ResultState
from rochade.trf.results import RESULT_CODES, UNPLAYED_CODES

router = APIRouter(prefix="/games", tags=["arbiter"])


class SetResultResult(BaseModel):
    game_id: uuid.UUID
    state: ResultState
    white_result: str
    black_result: str


class SetResult(Command):
    access = Access.ARBITER
    result_model = SetResultResult

    game_id: uuid.UUID
    #: Raw TRF codes, one per side. The arbiter's vocabulary is the file's
    #: vocabulary -- a double forfeit is ("-", "-") and has no other spelling.
    white_result: str = Field(min_length=1, max_length=1)
    black_result: str = Field(default=" ", min_length=1, max_length=1)
    note: str = Field(default="", max_length=500)

    @field_validator("white_result", "black_result")
    @classmethod
    def _known_code(cls, value: str) -> str:
        if value not in RESULT_CODES:
            raise ValueError(f"unknown TRF result code {value!r}")
        return value

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_game(session, self.game_id)


@bus.register(SetResult)
def handle(command: SetResult, ctx: Context) -> SetResultResult:
    round_, game = lock_round_of_game(ctx, command.game_id)
    require_open(round_, arbiter=True)

    if game.black_rank is None:
        if command.white_result not in UNPLAYED_CODES:
            raise ValidationFailed(
                "this board is a bye, so it can only carry an unplayed-game code",
                allowed=sorted(UNPLAYED_CODES),
            )
        if command.black_result != " ":
            raise ValidationFailed("a bye has no opponent side to score")

    previous = (game.white_result, game.black_result, game.state)
    game.white_result = command.white_result
    game.black_result = command.black_result
    game.state = ResultState.CONFIRMED
    game.disputed_white_result = None

    record(
        ctx,
        section_id=round_.section_id,
        round_number=round_.number,
        action=EventAction.RESULT_SET,
        game=game,
        board=game.board,
        previous={"white": previous[0], "black": previous[1], "state": previous[2].value},
        white_result=game.white_result,
        black_result=game.black_result,
        note=command.note,
    )

    return SetResultResult(
        game_id=game.id,
        state=game.state,
        white_result=game.white_result,
        black_result=game.black_result,
    )


class SetResultBody(BaseModel):
    white_result: str
    black_result: str = " "
    note: str = ""


@router.put("/{game_id}/result", response_model=SetResultResult)
def set_result(
    game_id: uuid.UUID, body: SetResultBody, ctx: Context = Depends(get_context)
) -> SetResultResult:
    result: SetResultResult = bus.send(SetResult(game_id=game_id, **body.model_dump()), ctx)
    return result
