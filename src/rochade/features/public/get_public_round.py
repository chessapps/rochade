"""The boards of one round, with results as far as they can be trusted."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from rochade.features.public.shown import (
    Shown,
    Side,
    cacheable,
    published_tournament,
    section_of,
    shown_result,
    shown_state,
    side_from_game,
    sides_of,
)
from rochade.platform.bus import bus
from rochade.platform.errors import NotFound
from rochade.platform.http import get_public_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.enums import RoundState

router = APIRouter(prefix="/public/tournaments", tags=["public"])


class PublicBoard(BaseModel):
    board: int
    white: Side
    #: None for a bye.
    black: Side | None
    #: As printed: ``1-0``, ``½-½``, ``0-1``, ``+:-``; a bye's score; blank while pending.
    result: str
    state: Shown
    updated_at: datetime


class PublicRound(BaseModel):
    section_id: uuid.UUID
    section_name: str
    number: int
    state: RoundState
    boards: list[PublicBoard] = Field(default_factory=list)


class GetPublicRound(Query):
    access = Access.PUBLIC

    slug: str
    section_id: uuid.UUID
    number: int


@bus.register(GetPublicRound)
def handle(query: GetPublicRound, ctx: Context) -> PublicRound:
    tournament = published_tournament(ctx.session, query.slug)
    section = section_of(tournament, query.section_id)
    round_ = next((r for r in section.rounds if r.number == query.number), None)
    if round_ is None:
        raise NotFound("round not found", number=query.number)

    sides = sides_of(section)
    return PublicRound(
        section_id=section.id,
        section_name=section.name,
        number=round_.number,
        state=round_.state,
        boards=[
            PublicBoard(
                board=game.board,
                white=side_from_game(sides, game.white_rank, game.white_name),
                black=(
                    side_from_game(sides, game.black_rank, game.black_name or "")
                    if game.black_rank is not None
                    else None
                ),
                result=shown_result(game),
                state=shown_state(game, round_),
                updated_at=game.updated_at,
            )
            for game in sorted(round_.games, key=lambda g: g.board)
        ],
    )


@router.get("/{slug}/sections/{section_id}/rounds/{number}", response_model=PublicRound)
def get_public_round(
    slug: str,
    section_id: uuid.UUID,
    number: int,
    response: Response,
    ctx: Context = Depends(get_public_context),
) -> PublicRound:
    result: PublicRound = bus.send(
        GetPublicRound(slug=slug, section_id=section_id, number=number), ctx
    )
    cacheable(response)
    return result
