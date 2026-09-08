"""The standings as the manager last handed them over.

Nothing here is computed: points, tiebreaks and ranks are the manager's own
numbers, read out of its player list at import time. The one thing Seebach adds
is the labelling -- which round they are current for, and what the tiebreak
columns are called, if the arbiter has said.

Readable by a device so the hall app can show the table, and by staff.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from seebach.interchange import UnknownManager, manager_for
from seebach.platform.bus import bus
from seebach.platform.errors import NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Context, Query
from seebach.shared.enums import RoundState
from seebach.shared.models import Section, Tournament

router = APIRouter(prefix="/tournaments", tags=["standings"])


class StandingRow(BaseModel):
    rank: int
    start_rank: int
    name: str
    title: str
    federation: str
    rating: int | None
    points: float
    #: Aligned with the section's `tiebreak_names`; None where the file was empty.
    tiebreaks: list[float | None]


class SectionStandings(BaseModel):
    section_id: uuid.UUID
    section_name: str
    manager_label: str
    #: The round the table is current for; 0 is the starting order.
    after_round: int
    #: The newest round we hold, so a screen can say "round 5 in play".
    rounds_held: int
    #: True when a newer round has been exported back since the standings
    #: arrived, so a fresh player list would change the table.
    stale: bool
    tiebreak_names: list[str]
    tiebreak_columns: int
    rows: list[StandingRow]


class TournamentStandings(BaseModel):
    tournament_id: uuid.UUID
    tournament_name: str
    sections: list[SectionStandings] = Field(default_factory=list)


class GetStandings(Query):
    access = Access.DEVICE

    tournament_id: uuid.UUID


@bus.register(GetStandings)
def handle(query: GetStandings, ctx: Context) -> TournamentStandings:
    tournament = ctx.session.get(Tournament, query.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(query.tournament_id))

    sections = ctx.session.scalars(
        select(Section).where(Section.tournament_id == tournament.id).order_by(Section.name)
    ).all()

    return TournamentStandings(
        tournament_id=tournament.id,
        tournament_name=tournament.name,
        sections=[
            standings_of(section)
            for section in sections
            if section.standings_after_round is not None
        ],
    )


def standings_of(section: Section) -> SectionStandings:
    try:
        label = manager_for(section.manager).label
    except UnknownManager:  # pragma: no cover - an adapter was removed after import
        label = section.manager

    ranked = [p for p in section.players if p.rank is not None]
    rows = [
        StandingRow(
            rank=p.rank or 0,
            start_rank=p.start_rank,
            name=p.name,
            title=p.title,
            federation=p.federation,
            rating=p.rating,
            points=p.points or 0.0,
            tiebreaks=list(p.tiebreaks or []),
        )
        for p in sorted(ranked, key=lambda p: (p.rank or 0, p.start_rank))
    ]
    columns = max((len(r.tiebreaks) for r in rows), default=0)
    after = section.standings_after_round or 0
    exported = max((r.number for r in section.rounds if r.state is RoundState.EXPORTED), default=0)
    return SectionStandings(
        section_id=section.id,
        section_name=section.name,
        manager_label=label,
        after_round=after,
        rounds_held=max((r.number for r in section.rounds), default=0),
        stale=exported > after,
        tiebreak_names=list(section.tiebreak_names or []),
        tiebreak_columns=columns,
        rows=rows,
    )


@router.get("/{tournament_id}/standings", response_model=TournamentStandings)
def get_standings(
    tournament_id: uuid.UUID, ctx: Context = Depends(get_context)
) -> TournamentStandings:
    result: TournamentStandings = bus.send(GetStandings(tournament_id=tournament_id), ctx)
    return result
