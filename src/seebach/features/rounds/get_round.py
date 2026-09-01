"""Every board in one round, for the arbiter's round view."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from seebach.features.scoping import tournament_of_round
from seebach.platform.bus import bus
from seebach.platform.errors import NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Context, Query
from seebach.shared.enums import ResultState, RoundState
from seebach.shared.models import Round

router = APIRouter(prefix="/rounds", tags=["arbiter"])


class BoardDetail(BaseModel):
    game_id: uuid.UUID
    board: int
    white_rank: int
    white_name: str
    black_rank: int | None
    black_name: str | None
    white_result: str
    black_result: str
    disputed_white_result: str | None
    state: ResultState
    is_bye: bool
    updated_at: datetime


class RoundDetail(BaseModel):
    id: uuid.UUID
    number: int
    state: RoundState
    section_id: uuid.UUID
    section_name: str
    source_filename: str
    imported_at: datetime | None
    released_at: datetime | None
    exported_at: datetime | None
    boards: list[BoardDetail]


class GetRound(Query):
    access = Access.STAFF

    round_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_round(session, self.round_id)


@bus.register(GetRound)
def handle(query: GetRound, ctx: Context) -> RoundDetail:
    round_ = ctx.session.get(Round, query.round_id)
    if round_ is None:
        raise NotFound("round not found", round_id=str(query.round_id))

    return RoundDetail(
        id=round_.id,
        number=round_.number,
        state=round_.state,
        section_id=round_.section_id,
        section_name=round_.section.name,
        source_filename=round_.source_filename,
        imported_at=round_.imported_at,
        released_at=round_.released_at,
        exported_at=round_.exported_at,
        boards=[
            BoardDetail(
                game_id=game.id,
                board=game.board,
                white_rank=game.white_rank,
                white_name=game.white_name,
                black_rank=game.black_rank,
                black_name=game.black_name,
                white_result=game.white_result,
                black_result=game.black_result,
                disputed_white_result=game.disputed_white_result,
                state=game.state,
                is_bye=game.black_rank is None,
                updated_at=game.updated_at,
            )
            for game in round_.games
        ],
    )


@router.get("/{round_id}", response_model=RoundDetail)
def get_round(round_id: uuid.UUID, ctx: Context = Depends(get_context)) -> RoundDetail:
    result: RoundDetail = bus.send(GetRound(round_id=round_id), ctx)
    return result
