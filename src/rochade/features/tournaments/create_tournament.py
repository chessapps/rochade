"""Create a tournament shell.

Deliberately thin. The pairing program owns setup, the player list and the
pairings; all this does is give the imports somewhere to land and give staff
something to be a member of.

The one real decision made here is which program that is. It is fixed for the
tournament's life: every import and export goes to it, so the arbiter is never
asked for a Vega file in a Swiss-Manager tournament or the other way round.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from rochade.interchange import UnknownManager, available, manager_for
from rochade.platform.bus import bus
from rochade.platform.errors import ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import Role
from rochade.shared.models import Tournament, TournamentMember

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


class CreateTournamentResult(BaseModel):
    id: uuid.UUID
    name: str


class CreateTournament(Command):
    access = Access.STAFF
    result_model = CreateTournamentResult

    name: str = Field(min_length=1, max_length=255)
    #: Key of the pairing program, from `GET /api/managers`.
    manager: str = Field(min_length=1, max_length=32)
    city: str = Field(default="", max_length=120)
    federation: str = Field(default="", max_length=8)
    start_date: date | None = None
    end_date: date | None = None

    def tournament_scope(self, session: object) -> uuid.UUID | None:
        # Nothing to scope to yet -- the creator becomes its owner below.
        return None

    def check(self) -> None:
        try:
            manager_for(self.manager)
        except UnknownManager:
            raise ValidationFailed(
                f"no pairing program named {self.manager!r}",
                manager=self.manager,
                available=[m.key for m in available()],
            ) from None
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationFailed("the tournament ends before it starts")


@bus.register(CreateTournament)
def handle(command: CreateTournament, ctx: Context) -> CreateTournamentResult:
    tournament = Tournament(
        name=command.name,
        manager=command.manager,
        city=command.city,
        federation=command.federation,
        start_date=command.start_date,
        end_date=command.end_date,
    )
    ctx.session.add(tournament)
    ctx.session.flush()

    if ctx.principal.is_staff:
        ctx.session.add(
            TournamentMember(
                tournament_id=tournament.id,
                subject=ctx.principal.subject,
                role=Role.OWNER,
            )
        )
    return CreateTournamentResult(id=tournament.id, name=tournament.name)


@router.post("", response_model=CreateTournamentResult, status_code=201)
def create_tournament(
    command: CreateTournament, ctx: Context = Depends(get_context)
) -> CreateTournamentResult:
    result: CreateTournamentResult = bus.send(command, ctx)
    return result
