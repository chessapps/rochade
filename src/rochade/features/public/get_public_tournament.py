"""One published tournament: its sections and where each round stands."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from rochade.features.public.shown import cacheable, published_tournament
from rochade.platform.bus import bus
from rochade.platform.http import get_public_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.enums import RoundState
from rochade.shared.models import Game, Round, Section

router = APIRouter(prefix="/public/tournaments", tags=["public"])


class PublicRoundSummary(BaseModel):
    number: int
    state: RoundState
    #: Boards with two players, and how many of them show a result.
    boards: int
    results_in: int
    #: When the last result on it changed, for a "last updated" line.
    updated_at: datetime | None


class PublicSection(BaseModel):
    id: uuid.UUID
    name: str
    players: int
    declared_rounds: int | None
    #: The round the standings are current for; None when none were imported.
    standings_after_round: int | None
    tiebreak_names: list[str]
    rounds: list[PublicRoundSummary]


class PublicTournament(BaseModel):
    slug: str
    name: str
    city: str
    federation: str
    start_date: date | None
    end_date: date | None
    sections: list[PublicSection]


class GetPublicTournament(Query):
    access = Access.PUBLIC

    slug: str


@bus.register(GetPublicTournament)
def handle(query: GetPublicTournament, ctx: Context) -> PublicTournament:
    tournament = published_tournament(ctx.session, query.slug)

    rows = ctx.session.execute(
        select(
            Game.round_id,
            func.count(Game.id).filter(Game.black_rank.is_not(None)),
            func.count(Game.id).filter(Game.black_rank.is_not(None), Game.white_result != " "),
            func.max(Game.updated_at),
        )
        .join(Round, Round.id == Game.round_id)
        .join(Section, Section.id == Round.section_id)
        .where(Section.tournament_id == tournament.id)
        .group_by(Game.round_id)
    ).all()
    counts = {
        round_id: (int(boards), int(results), updated)
        for round_id, boards, results, updated in rows
    }

    return PublicTournament(
        slug=tournament.slug or "",
        name=tournament.name,
        city=tournament.city,
        federation=tournament.federation,
        start_date=tournament.start_date,
        end_date=tournament.end_date,
        sections=[
            PublicSection(
                id=section.id,
                name=section.name,
                players=len(section.players),
                declared_rounds=section.declared_rounds,
                standings_after_round=section.standings_after_round,
                tiebreak_names=list(section.tiebreak_names or []),
                rounds=[
                    PublicRoundSummary(
                        number=round_.number,
                        state=round_.state,
                        boards=counts.get(round_.id, (0, 0, None))[0],
                        results_in=counts.get(round_.id, (0, 0, None))[1],
                        updated_at=counts.get(round_.id, (0, 0, None))[2],
                    )
                    for round_ in sorted(section.rounds, key=lambda r: r.number)
                ],
            )
            for section in tournament.sections
        ],
    )


@router.get("/{slug}", response_model=PublicTournament)
def get_public_tournament(
    slug: str, response: Response, ctx: Context = Depends(get_public_context)
) -> PublicTournament:
    result: PublicTournament = bus.send(GetPublicTournament(slug=slug), ctx)
    cacheable(response)
    return result
