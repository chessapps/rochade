"""One tournament, its sections, and where each round stands.

The shape an arbiter needs to answer the two questions they actually have:
which round is open, and is it ready to send back to Vega.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rochade.interchange import label_of, native_of
from rochade.platform.bus import bus
from rochade.platform.errors import NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.enums import ResultState, RoundState
from rochade.shared.models import Game, Round, Section, SectionPlayer, Tournament

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


class RoundSummary(BaseModel):
    id: uuid.UUID
    number: int
    state: RoundState
    #: Boards with two players. Byes are counted apart: nobody enters them and
    #: they never need the arbiter, so they belong in no progress figure.
    boards: int
    byes: int
    empty: int
    claimed: int
    disputed: int
    confirmed: int
    imported_at: datetime | None
    released_at: datetime | None
    exported_at: datetime | None

    @property
    def ready_to_release(self) -> bool:
        return self.empty == 0 and self.disputed == 0


class SectionSummary(BaseModel):
    id: uuid.UUID
    name: str
    #: Which manager adapter owns this section -- the export button says so.
    manager: str
    manager_label: str
    #: Rochade pairs this section itself: no import, no export, a pairing instead.
    native: bool
    players: int
    declared_rounds: int | None
    rounds: list[RoundSummary]


class TournamentDetail(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    federation: str
    start_date: date | None
    end_date: date | None
    #: The pairing program every section imports from and exports to.
    manager: str
    manager_label: str
    native: bool
    #: The code a phone may type instead of scanning; None when that is closed.
    #: Staff-only, like everything else on this query.
    join_code: str | None = None
    sections: list[SectionSummary]


class GetTournament(Query):
    access = Access.STAFF

    tournament_id: uuid.UUID


@bus.register(GetTournament)
def handle(query: GetTournament, ctx: Context) -> TournamentDetail:
    tournament = ctx.session.get(Tournament, query.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(query.tournament_id))

    counts = _round_counts(ctx.session, query.tournament_id)
    player_counts: dict[uuid.UUID, int] = {
        section_id: int(count)
        for section_id, count in ctx.session.execute(
            select(SectionPlayer.section_id, func.count(SectionPlayer.id))
            .join(Section, Section.id == SectionPlayer.section_id)
            .where(Section.tournament_id == query.tournament_id)
            .group_by(SectionPlayer.section_id)
        ).all()
    }

    sections = [
        SectionSummary(
            id=section.id,
            name=section.name,
            manager=section.manager,
            manager_label=label_of(section.manager),
            native=native_of(section.manager),
            players=player_counts.get(section.id, 0),
            declared_rounds=section.declared_rounds,
            rounds=[
                RoundSummary(
                    id=round_.id,
                    number=round_.number,
                    state=round_.state,
                    imported_at=round_.imported_at,
                    released_at=round_.released_at,
                    exported_at=round_.exported_at,
                    **counts.get(round_.id, _ZERO),
                )
                for round_ in section.rounds
            ],
        )
        for section in tournament.sections
    ]

    return TournamentDetail(
        id=tournament.id,
        name=tournament.name,
        city=tournament.city,
        federation=tournament.federation,
        manager=tournament.manager,
        manager_label=label_of(tournament.manager),
        native=native_of(tournament.manager),
        join_code=tournament.join_code,
        start_date=tournament.start_date,
        end_date=tournament.end_date,
        sections=sections,
    )


_ZERO = {"boards": 0, "byes": 0, "empty": 0, "claimed": 0, "disputed": 0, "confirmed": 0}


def _round_counts(session: Session, tournament_id: uuid.UUID) -> dict[uuid.UUID, dict[str, int]]:
    rows = session.execute(
        select(Game.round_id, Game.state, Game.black_rank.is_(None), func.count(Game.id))
        .join(Round, Round.id == Game.round_id)
        .join(Section, Section.id == Round.section_id)
        .where(Section.tournament_id == tournament_id)
        .group_by(Game.round_id, Game.state, Game.black_rank.is_(None))
    ).all()

    counts: dict[uuid.UUID, dict[str, int]] = {}
    for round_id, state, is_bye, count in rows:
        bucket = counts.setdefault(round_id, dict(_ZERO))
        if is_bye:
            bucket["byes"] += int(count)
            continue
        bucket[ResultState(state).value] += int(count)
        bucket["boards"] += int(count)
    return counts


@router.get("/{tournament_id}", response_model=TournamentDetail)
def get_tournament(
    tournament_id: uuid.UUID, ctx: Context = Depends(get_context)
) -> TournamentDetail:
    result: TournamentDetail = bus.send(GetTournament(tournament_id=tournament_id), ctx)
    return result
