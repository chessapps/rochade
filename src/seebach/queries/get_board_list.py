"""The board list the hall app shows: every open board in the tournament.

Across all sections at once. That is the thing Vega cannot do -- it is one
tournament per file -- and it is why a player can just type their name instead
of first working out which group's list to look at.

Search is done here rather than in the client because the client is offline
half the time and caches this response whole; the `q` filter is for the arbiter
poking at it, not for the phone.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi import Query as QueryParam
from pydantic import BaseModel, Field
from sqlalchemy import select

from seebach.platform.bus import bus
from seebach.platform.errors import NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Context, Query
from seebach.shared.enums import ResultState, RoundState
from seebach.shared.models import Game, Round, Section, Tournament

router = APIRouter(prefix="/tournaments", tags=["hall"])


class HallBoard(BaseModel):
    game_id: uuid.UUID
    section_id: uuid.UUID
    section_name: str
    round_number: int
    board: int
    white_name: str
    black_name: str | None
    white_result: str
    state: ResultState
    is_bye: bool
    #: True once a result stands, so the phone can grey the row out.
    entered: bool


class HallBoardList(BaseModel):
    tournament_id: uuid.UUID
    tournament_name: str
    #: Bumped whenever any board changes, so a cached client can tell it is stale.
    generated_at: datetime
    open_rounds: list[int] = Field(default_factory=list)
    boards: list[HallBoard] = Field(default_factory=list)


class GetBoardList(Query):
    access = Access.DEVICE

    tournament_id: uuid.UUID
    q: str = ""


@bus.register(GetBoardList)
def handle(query: GetBoardList, ctx: Context) -> HallBoardList:
    tournament = ctx.session.get(Tournament, query.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(query.tournament_id))

    rows = ctx.session.execute(
        select(
            Game.id,
            Section.id,
            Section.name,
            Round.number,
            Game.board,
            Game.white_name,
            Game.black_name,
            Game.white_result,
            Game.state,
            Game.black_rank,
        )
        .join(Round, Round.id == Game.round_id)
        .join(Section, Section.id == Round.section_id)
        .where(Section.tournament_id == query.tournament_id, Round.state == RoundState.OPEN)
        .order_by(Section.name, Round.number, Game.board)
    ).all()

    needle = query.q.strip().casefold()
    boards = [
        HallBoard(
            game_id=row[0],
            section_id=row[1],
            section_name=row[2],
            round_number=row[3],
            board=row[4],
            white_name=row[5],
            black_name=row[6],
            white_result=row[7],
            state=ResultState(row[8]),
            is_bye=row[9] is None,
            entered=ResultState(row[8]) is not ResultState.EMPTY,
        )
        for row in rows
        if not needle or _matches(needle, row[5], row[6])
    ]

    return HallBoardList(
        tournament_id=tournament.id,
        tournament_name=tournament.name,
        generated_at=datetime.now(),
        open_rounds=sorted({b.round_number for b in boards}),
        boards=boards,
    )


def _matches(needle: str, white: str, black: str | None) -> bool:
    return needle in white.casefold() or (black is not None and needle in black.casefold())


@router.get("/{tournament_id}/boards", response_model=HallBoardList)
def get_board_list(
    tournament_id: uuid.UUID,
    q: str = QueryParam(default=""),
    ctx: Context = Depends(get_context),
) -> HallBoardList:
    result: HallBoardList = bus.send(GetBoardList(tournament_id=tournament_id, q=q), ctx)
    return result
