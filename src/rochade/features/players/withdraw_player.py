"""A player leaves the event, or comes back.

Withdrawal is from a round on: the player is left out of every pairing from
there, and the rounds they miss are absences in the table. It can only start
at a round that is not yet paired -- a board already on the wall is settled
with a result, a forfeit if need be, not by making the player vanish.

Reinstating clears it. A round already paired without the player stays
as it is; they are paired again from the next one, and the audit line says
which.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.players.list_players import PlayerDetail, editable_section, player_detail
from rochade.features.scoping import tournament_of_player
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction
from rochade.shared.models import SectionPlayer

router = APIRouter(prefix="/players", tags=["players"])


class WithdrawPlayer(Command):
    access = Access.ARBITER
    result_model = PlayerDetail

    player_id: uuid.UUID
    #: The first round the player misses. None means the next unpaired round.
    from_round: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=500)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_player(session, self.player_id)


@bus.register(WithdrawPlayer)
def handle(command: WithdrawPlayer, ctx: Context) -> PlayerDetail:
    player = ctx.session.get(SectionPlayer, command.player_id)
    if player is None:
        raise NotFound("player not found", player_id=str(command.player_id))
    section = editable_section(ctx, player.section_id)

    next_unpaired = max((r.number for r in section.rounds), default=0) + 1
    from_round = command.from_round if command.from_round is not None else next_unpaired
    if from_round < next_unpaired:
        raise Conflict(
            f"round {from_round} is already paired; settle that board with a result "
            f"and withdraw the player from round {next_unpaired}",
            next_unpaired=next_unpaired,
        )
    if player.withdrawn_from_round is not None and player.withdrawn_from_round <= from_round:
        raise Conflict(
            f"this player is already withdrawn from round {player.withdrawn_from_round}",
            withdrawn_from_round=player.withdrawn_from_round,
        )

    player.withdrawn_from_round = from_round
    ctx.session.flush()
    record(
        ctx,
        section_id=section.id,
        round_number=from_round,
        action=EventAction.PLAYER_WITHDRAWN,
        start_rank=player.start_rank,
        name=player.name,
        from_round=from_round,
        note=command.note,
    )
    return player_detail(player)


class ReinstatePlayer(Command):
    access = Access.ARBITER
    result_model = PlayerDetail

    player_id: uuid.UUID
    note: str = Field(default="", max_length=500)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_player(session, self.player_id)


@bus.register(ReinstatePlayer)
def handle_reinstate(command: ReinstatePlayer, ctx: Context) -> PlayerDetail:
    player = ctx.session.get(SectionPlayer, command.player_id)
    if player is None:
        raise NotFound("player not found", player_id=str(command.player_id))
    section = editable_section(ctx, player.section_id)

    if player.withdrawn_from_round is None:
        raise Conflict("this player has not been withdrawn", name=player.name)
    next_unpaired = max((r.number for r in section.rounds), default=0) + 1
    was = player.withdrawn_from_round
    player.withdrawn_from_round = None
    ctx.session.flush()
    record(
        ctx,
        section_id=section.id,
        round_number=next_unpaired,
        action=EventAction.PLAYER_REINSTATED,
        start_rank=player.start_rank,
        name=player.name,
        was_withdrawn_from_round=was,
        paired_again_from_round=next_unpaired,
        note=command.note,
    )
    return player_detail(player)


class WithdrawBody(BaseModel):
    from_round: int | None = None
    note: str = ""


class ReinstateBody(BaseModel):
    note: str = ""


@router.post("/{player_id}/withdraw", response_model=PlayerDetail)
def withdraw_player(
    player_id: uuid.UUID, body: WithdrawBody, ctx: Context = Depends(get_context)
) -> PlayerDetail:
    result: PlayerDetail = bus.send(WithdrawPlayer(player_id=player_id, **body.model_dump()), ctx)
    return result


@router.post("/{player_id}/reinstate", response_model=PlayerDetail)
def reinstate_player(
    player_id: uuid.UUID, body: ReinstateBody, ctx: Context = Depends(get_context)
) -> PlayerDetail:
    result: PlayerDetail = bus.send(ReinstatePlayer(player_id=player_id, **body.model_dump()), ctx)
    return result
