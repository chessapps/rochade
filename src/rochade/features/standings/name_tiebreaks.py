"""What the manager's tiebreak columns are called.

Swiss-Manager's export numbers them `Wtg1`.. and says nothing else; the
tournament's settings know, and so does the arbiter. Typed in once, shown on
every table from then on.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.platform.bus import bus
from rochade.platform.errors import NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.models import Section

router = APIRouter(prefix="/tournaments", tags=["standings"])


class TiebreakNamesResult(BaseModel):
    section_name: str
    tiebreak_names: list[str]


class NameTiebreaks(Command):
    access = Access.ARBITER
    result_model = TiebreakNamesResult

    tournament_id: uuid.UUID
    section_name: str = Field(min_length=1, max_length=120)
    names: list[str] = Field(default_factory=list, max_length=9)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return self.tournament_id


@bus.register(NameTiebreaks)
def handle(command: NameTiebreaks, ctx: Context) -> TiebreakNamesResult:
    section = ctx.session.scalar(
        select(Section).where(
            Section.tournament_id == command.tournament_id,
            Section.name == command.section_name,
        )
    )
    if section is None:
        raise NotFound("section not found", section_name=command.section_name)

    names = [name.strip()[:40] for name in command.names]
    while names and not names[-1]:
        names.pop()
    section.tiebreak_names = names
    ctx.session.flush()
    return TiebreakNamesResult(section_name=section.name, tiebreak_names=names)


class TiebreakNamesBody(BaseModel):
    names: list[str] = Field(default_factory=list)


@router.put(
    "/{tournament_id}/sections/{section_name}/tiebreaks", response_model=TiebreakNamesResult
)
def name_tiebreaks(
    tournament_id: uuid.UUID,
    section_name: str,
    body: TiebreakNamesBody,
    ctx: Context = Depends(get_context),
) -> TiebreakNamesResult:
    result: TiebreakNamesResult = bus.send(
        NameTiebreaks(tournament_id=tournament_id, section_name=section_name, names=body.names),
        ctx,
    )
    return result
