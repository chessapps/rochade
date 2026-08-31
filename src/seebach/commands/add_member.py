"""Grant a staff account a role on one tournament.

Access is per tournament, never global: an arbiter for the club championship is
not thereby an arbiter for anything else.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from seebach.platform.bus import bus
from seebach.platform.errors import NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import Role
from seebach.shared.models import Tournament, TournamentMember

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


class MemberResult(BaseModel):
    id: uuid.UUID
    subject: str
    role: Role


class AddMember(Command):
    access = Access.OWNER
    result_model = MemberResult

    tournament_id: uuid.UUID
    subject: str = Field(min_length=1, max_length=255)
    display_name: str = Field(default="", max_length=255)
    role: Role = Role.ARBITER


@bus.register(AddMember)
def handle(command: AddMember, ctx: Context) -> MemberResult:
    if ctx.session.get(Tournament, command.tournament_id) is None:
        raise NotFound("tournament not found", tournament_id=str(command.tournament_id))

    member = ctx.session.scalar(
        select(TournamentMember).where(
            TournamentMember.tournament_id == command.tournament_id,
            TournamentMember.subject == command.subject,
        )
    )
    if member is None:
        member = TournamentMember(
            tournament_id=command.tournament_id,
            subject=command.subject,
            display_name=command.display_name,
            role=command.role,
        )
        ctx.session.add(member)
        ctx.session.flush()
    else:
        member.role = command.role
        member.display_name = command.display_name or member.display_name

    return MemberResult(id=member.id, subject=member.subject, role=member.role)


@router.post("/{tournament_id}/members", response_model=MemberResult, status_code=201)
def add_member(
    tournament_id: uuid.UUID, body: AddMember, ctx: Context = Depends(get_context)
) -> MemberResult:
    command = body.model_copy(update={"tournament_id": tournament_id})
    result: MemberResult = bus.send(command, ctx)
    return result
