"""One player and every game they played in the tournament."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from rochade.features.public.shown import (
    Shown,
    Side,
    cacheable,
    player_of,
    points_of,
    published_tournament,
    section_of,
    shown_result,
    shown_state,
    side_from_game,
    sides_of,
)
from rochade.platform.bus import bus
from rochade.platform.http import get_public_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.enums import Colour

router = APIRouter(prefix="/public/tournaments", tags=["public"])


class PublicGame(BaseModel):
    round_number: int
    board: int
    #: None for a bye.
    colour: Colour | None
    opponent: Side | None
    #: The board's result as printed, white first, whichever colour this player had.
    result: str
    #: This player's points from the game; None while pending.
    score: float | None
    state: Shown
    updated_at: datetime


class PublicPlayer(BaseModel):
    section_id: uuid.UUID
    section_name: str
    start_rank: int
    name: str
    title: str
    rating: int | None
    federation: str
    withdrawn_from_round: int | None
    #: From the manager's standings; None when none were imported.
    rank: int | None
    points: float | None
    tiebreaks: list[float | None]
    tiebreak_names: list[str]
    standings_after_round: int | None
    games: list[PublicGame] = Field(default_factory=list)


class GetPublicPlayer(Query):
    access = Access.PUBLIC

    slug: str
    section_id: uuid.UUID
    start_rank: int


@bus.register(GetPublicPlayer)
def handle(query: GetPublicPlayer, ctx: Context) -> PublicPlayer:
    tournament = published_tournament(ctx.session, query.slug)
    section = section_of(tournament, query.section_id)
    player = player_of(section, query.start_rank)
    sides = sides_of(section)

    games: list[PublicGame] = []
    for round_ in sorted(section.rounds, key=lambda r: r.number):
        for game in round_.games:
            if game.white_rank == player.start_rank:
                colour: Colour | None = Colour.WHITE if game.black_rank is not None else None
                own, opponent = (
                    game.white_result,
                    (
                        side_from_game(sides, game.black_rank, game.black_name or "")
                        if game.black_rank is not None
                        else None
                    ),
                )
            elif game.black_rank == player.start_rank:
                colour = Colour.BLACK
                own = game.black_result
                opponent = side_from_game(sides, game.white_rank, game.white_name)
            else:
                continue
            games.append(
                PublicGame(
                    round_number=round_.number,
                    board=game.board,
                    colour=colour,
                    opponent=opponent,
                    result=shown_result(game),
                    score=points_of(own),
                    state=shown_state(game, round_),
                    updated_at=game.updated_at,
                )
            )

    return PublicPlayer(
        section_id=section.id,
        section_name=section.name,
        start_rank=player.start_rank,
        name=player.name,
        title=player.title,
        rating=player.rating,
        federation=player.federation,
        withdrawn_from_round=player.withdrawn_from_round,
        rank=player.rank,
        points=player.points,
        tiebreaks=list(player.tiebreaks or []),
        tiebreak_names=list(section.tiebreak_names or []),
        standings_after_round=section.standings_after_round,
        games=games,
    )


@router.get("/{slug}/sections/{section_id}/players/{start_rank}", response_model=PublicPlayer)
def get_public_player(
    slug: str,
    section_id: uuid.UUID,
    start_rank: int,
    response: Response,
    ctx: Context = Depends(get_public_context),
) -> PublicPlayer:
    result: PublicPlayer = bus.send(
        GetPublicPlayer(slug=slug, section_id=section_id, start_rank=start_rank), ctx
    )
    cacheable(response)
    return result
