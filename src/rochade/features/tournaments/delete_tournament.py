"""Delete a tournament and everything under it.

The one irreversible action on the desk. Sections, players, rounds, games,
the audit log, device tokens and memberships all go with it -- the database
cascades, so a half-deleted tournament cannot exist.

The caller has to say the tournament's name back, exactly. That is not a
password: anyone allowed here already knows the name. It is a check that the
request means *this* tournament, so a stale id or a mis-clicked list cannot
take a whole event with it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from rochade.platform.bus import bus
from rochade.platform.errors import NotFound, ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.models import Tournament

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


class DeleteTournamentResult(BaseModel):
    id: uuid.UUID
    name: str


class DeleteTournament(Command):
    access = Access.OWNER
    result_model = DeleteTournamentResult

    tournament_id: uuid.UUID
    #: The tournament's name, typed back by the caller.
    confirm_name: str = Field(min_length=1, max_length=255)


@bus.register(DeleteTournament)
def handle(command: DeleteTournament, ctx: Context) -> DeleteTournamentResult:
    tournament = ctx.session.get(Tournament, command.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(command.tournament_id))
    if command.confirm_name.strip() != tournament.name:
        raise ValidationFailed(
            "the name does not match; type the tournament's name exactly to delete it",
            expected=tournament.name,
        )

    result = DeleteTournamentResult(id=tournament.id, name=tournament.name)
    ctx.session.delete(tournament)
    ctx.session.flush()
    return result


@router.delete("/{tournament_id}", response_model=DeleteTournamentResult)
def delete_tournament(
    tournament_id: uuid.UUID,
    confirm_name: str = Query(
        min_length=1,
        max_length=255,
        description="The tournament's name, repeated exactly, to confirm the deletion.",
    ),
    ctx: Context = Depends(get_context),
) -> DeleteTournamentResult:
    result: DeleteTournamentResult = bus.send(
        DeleteTournament(tournament_id=tournament_id, confirm_name=confirm_name), ctx
    )
    return result
