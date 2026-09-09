"""What the arbiter still has to look at, across the whole tournament.

Sorted by how much attention each board needs: disputes first, then boards
nobody entered, then claims that are merely waiting to be released. Confirming
a round should be a scan, not a data-entry session.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from rochade.platform.bus import bus
from rochade.platform.errors import NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.enums import ResultState, RoundState
from rochade.shared.models import Game, Round, Section, Tournament

router = APIRouter(prefix="/tournaments", tags=["arbiter"])

# Disputes are the only thing that cannot be resolved by waiting.
_URGENCY = {
    ResultState.DISPUTED: 0,
    ResultState.EMPTY: 1,
    ResultState.CLAIMED: 2,
    ResultState.CONFIRMED: 3,
}


class QueueEntry(BaseModel):
    game_id: uuid.UUID
    round_id: uuid.UUID
    section_name: str
    round_number: int
    board: int
    white_name: str
    black_name: str | None
    white_result: str
    disputed_white_result: str | None
    state: ResultState
    is_bye: bool
    updated_at: datetime


class ArbiterQueue(BaseModel):
    tournament_id: uuid.UUID
    disputed: int = 0
    empty: int = 0
    claimed: int = 0
    confirmed: int = 0
    entries: list[QueueEntry] = Field(default_factory=list)

    @property
    def blocking(self) -> int:
        return self.disputed + self.empty


class GetArbiterQueue(Query):
    access = Access.STAFF

    tournament_id: uuid.UUID
    # Confirmed boards are excluded by default -- they are not work.
    include_confirmed: bool = False


@bus.register(GetArbiterQueue)
def handle(query: GetArbiterQueue, ctx: Context) -> ArbiterQueue:
    if ctx.session.get(Tournament, query.tournament_id) is None:
        raise NotFound("tournament not found", tournament_id=str(query.tournament_id))

    rows = ctx.session.execute(
        select(Game, Section.name, Round.number, Round.id)
        .join(Round, Round.id == Game.round_id)
        .join(Section, Section.id == Round.section_id)
        .where(
            Section.tournament_id == query.tournament_id,
            Round.state == RoundState.OPEN,
        )
    ).all()

    queue = ArbiterQueue(tournament_id=query.tournament_id)
    entries: list[QueueEntry] = []
    for game, section_name, round_number, round_id in rows:
        setattr(queue, game.state.value, getattr(queue, game.state.value) + 1)
        if game.state is ResultState.CONFIRMED and not query.include_confirmed:
            continue
        entries.append(
            QueueEntry(
                game_id=game.id,
                round_id=round_id,
                section_name=section_name,
                round_number=round_number,
                board=game.board,
                white_name=game.white_name,
                black_name=game.black_name,
                white_result=game.white_result,
                disputed_white_result=game.disputed_white_result,
                state=game.state,
                is_bye=game.black_rank is None,
                updated_at=game.updated_at,
            )
        )

    queue.entries = sorted(
        entries, key=lambda e: (_URGENCY[e.state], e.section_name, e.round_number, e.board)
    )
    return queue


@router.get("/{tournament_id}/queue", response_model=ArbiterQueue)
def get_arbiter_queue(
    tournament_id: uuid.UUID,
    include_confirmed: bool = False,
    ctx: Context = Depends(get_context),
) -> ArbiterQueue:
    result: ArbiterQueue = bus.send(
        GetArbiterQueue(tournament_id=tournament_id, include_confirmed=include_confirmed), ctx
    )
    return result
