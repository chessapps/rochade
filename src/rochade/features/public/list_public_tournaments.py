"""The front door: every published tournament, the current ones first."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select

from rochade.features.public.shown import cacheable
from rochade.platform.bus import bus
from rochade.platform.http import get_public_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.enums import RoundState
from rochade.shared.models import Tournament

router = APIRouter(prefix="/public/tournaments", tags=["public"])


class PublicSectionSummary(BaseModel):
    id: uuid.UUID
    name: str
    #: The newest round held, and whether it is still being played.
    rounds_held: int
    in_play: bool
    declared_rounds: int | None


class PublicTournamentSummary(BaseModel):
    slug: str
    name: str
    city: str
    federation: str
    start_date: date | None
    end_date: date | None
    sections: list[PublicSectionSummary]


class ListPublicTournaments(Query):
    access = Access.PUBLIC


@bus.register(ListPublicTournaments)
def handle(query: ListPublicTournaments, ctx: Context) -> list[PublicTournamentSummary]:
    tournaments = ctx.session.scalars(
        select(Tournament)
        .where(Tournament.published.is_(True), Tournament.slug.is_not(None))
        .order_by(Tournament.start_date.desc().nullslast(), Tournament.name)
    ).all()
    summaries = [
        PublicTournamentSummary(
            slug=tournament.slug or "",
            name=tournament.name,
            city=tournament.city,
            federation=tournament.federation,
            start_date=tournament.start_date,
            end_date=tournament.end_date,
            sections=[
                PublicSectionSummary(
                    id=section.id,
                    name=section.name,
                    rounds_held=max((r.number for r in section.rounds), default=0),
                    in_play=any(r.state is RoundState.OPEN for r in section.rounds),
                    declared_rounds=section.declared_rounds,
                )
                for section in tournament.sections
            ],
        )
        for tournament in tournaments
    ]
    # A tournament with a round in play comes first, whatever its dates say.
    summaries.sort(key=lambda t: not any(s.in_play for s in t.sections))
    return summaries


@router.get("", response_model=list[PublicTournamentSummary])
def list_public_tournaments(
    response: Response, ctx: Context = Depends(get_public_context)
) -> list[PublicTournamentSummary]:
    result: list[PublicTournamentSummary] = bus.send(ListPublicTournaments(), ctx)
    cacheable(response)
    return result
