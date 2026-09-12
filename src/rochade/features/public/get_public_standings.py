"""A section's standings, the manager's numbers, for anyone."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response

from rochade.features.public.shown import cacheable, published_tournament, section_of
from rochade.features.standings.get_standings import SectionStandings, standings_of
from rochade.platform.bus import bus
from rochade.platform.http import get_public_context
from rochade.platform.mediator import Access, Context, Query

router = APIRouter(prefix="/public/tournaments", tags=["public"])


class GetPublicStandings(Query):
    access = Access.PUBLIC

    slug: str
    section_id: uuid.UUID


@bus.register(GetPublicStandings)
def handle(query: GetPublicStandings, ctx: Context) -> SectionStandings:
    tournament = published_tournament(ctx.session, query.slug)
    section = section_of(tournament, query.section_id)
    return standings_of(section)


@router.get("/{slug}/sections/{section_id}/standings", response_model=SectionStandings)
def get_public_standings(
    slug: str,
    section_id: uuid.UUID,
    response: Response,
    ctx: Context = Depends(get_public_context),
) -> SectionStandings:
    result: SectionStandings = bus.send(GetPublicStandings(slug=slug, section_id=section_id), ctx)
    cacheable(response)
    return result
