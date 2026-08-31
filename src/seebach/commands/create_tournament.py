"""Create a tournament shell.

Deliberately thin. Vega owns setup, the player list and the pairings; all this
does is give the imports somewhere to land and give staff something to be a
member of.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from seebach.platform.bus import bus
from seebach.platform.errors import ValidationFailed
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import Role
from seebach.shared.models import Tournament, TournamentMember

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


class CreateTournamentResult(BaseModel):
    id: uuid.UUID
    name: str


class CreateTournament(Command):
    access = Access.STAFF
    result_model = CreateTournamentResult

    name: str = Field(min_length=1, max_length=255)
    city: str = Field(default="", max_length=120)
    federation: str = Field(default="", max_length=8)
    start_date: date | None = None
    end_date: date | None = None

    def tournament_scope(self, session: object) -> uuid.UUID | None:
        # Nothing to scope to yet -- the creator becomes its owner below.
        return None

    def check(self) -> None:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationFailed("the tournament ends before it starts")


@bus.register(CreateTournament)
def handle(command: CreateTournament, ctx: Context) -> CreateTournamentResult:
    tournament = Tournament(
        name=command.name,
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
