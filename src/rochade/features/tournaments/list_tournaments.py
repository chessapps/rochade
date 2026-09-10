"""Tournaments the caller is a member of."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from rochade.interchange import label_of
from rochade.platform.bus import bus
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.enums import Role
from rochade.shared.models import Tournament, TournamentMember

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


class TournamentSummary(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    start_date: date | None
    end_date: date | None
    #: The pairing program the tournament runs on, key and display name.
    manager: str
    manager_label: str
    role: Role


class ListTournaments(Query):
    access = Access.STAFF


@bus.register(ListTournaments)
def handle(query: ListTournaments, ctx: Context) -> list[TournamentSummary]:
    rows = ctx.session.execute(
        select(
            Tournament.id,
            Tournament.name,
            Tournament.city,
            Tournament.manager,
            Tournament.start_date,
            Tournament.end_date,
            TournamentMember.role,
        )
        .join(TournamentMember, TournamentMember.tournament_id == Tournament.id)
        .where(TournamentMember.subject == ctx.principal.subject)
        .order_by(Tournament.start_date.desc().nullslast(), Tournament.name)
    ).all()
    return [
        TournamentSummary.model_validate(
            {**row._mapping, "manager_label": label_of(row._mapping["manager"])}
        )
        for row in rows
    ]


@router.get("", response_model=list[TournamentSummary])
def list_tournaments(ctx: Context = Depends(get_context)) -> list[TournamentSummary]:
    result: list[TournamentSummary] = bus.send(ListTournaments(), ctx)
    return result
