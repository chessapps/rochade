"""Correct a player's details.

Everything but the name moves freely: a rating typed wrong, a missing
federation. The name is different once the player has sat at a board -- it
is how the board, the phones' claims and the audit log name them -- so a
rename after that is refused rather than rewritten through the history.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.players.add_player import PlayerFields
from rochade.features.players.list_players import (
    PlayerDetail,
    editable_section,
    player_detail,
    same_name,
)
from rochade.features.scoping import tournament_of_player
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction
from rochade.shared.models import Game, Round, SectionPlayer

router = APIRouter(prefix="/players", tags=["players"])


class UpdatePlayer(PlayerFields, Command):
    access = Access.ARBITER
    result_model = PlayerDetail

    player_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_player(session, self.player_id)


@bus.register(UpdatePlayer)
def handle(command: UpdatePlayer, ctx: Context) -> PlayerDetail:
    player = ctx.session.get(SectionPlayer, command.player_id)
    if player is None:
        raise NotFound("player not found", player_id=str(command.player_id))
    section = editable_section(ctx, player.section_id)

    before = player_detail(player).model_dump(mode="json")
    if command.name != player.name:
        # Any change at all, a capital letter included: the boards, the
        # phones and the log carry the name exactly as it was written.
        if _has_played(ctx, player):
            raise Conflict(
                "this player has already been on a board under this name; "
                "withdraw them and add the new name as a new player instead",
                name=player.name,
            )
        clash = next(
            (p for p in section.players if p.id != player.id and same_name(p.name, command.name)),
            None,
        )
        if clash is not None:
            raise Conflict(
                "a player with this name is already in the section",
                name=clash.name,
                start_rank=clash.start_rank,
            )

    player.name = command.name
    player.title = command.title.upper()
    player.rating = command.rating
    player.federation = command.federation.upper()
    player.fide_id = command.fide_id
    player.sex = command.sex.lower().replace("f", "w")
    player.birth_date = command.birth_date
    ctx.session.flush()

    after = player_detail(player).model_dump(mode="json")
    changed = {key: [before[key], after[key]] for key in after if before[key] != after[key]}
    if changed:
        record(
            ctx,
            section_id=section.id,
            round_number=max((r.number for r in section.rounds), default=0),
            action=EventAction.PLAYER_UPDATED,
            start_rank=player.start_rank,
            name=player.name,
            changed=changed,
        )
    return player_detail(player)


def _has_played(ctx: Context, player: SectionPlayer) -> bool:
    """By start rank, which is what a board row records and what cannot drift."""
    on_a_board = (
        select(Game.id)
        .join(Round, Round.id == Game.round_id)
        .where(
            Round.section_id == player.section_id,
            or_(Game.white_rank == player.start_rank, Game.black_rank == player.start_rank),
        )
    )
    return bool(ctx.session.scalar(select(exists(on_a_board))))


@router.put("/{player_id}", response_model=PlayerDetail)
def update_player(
    player_id: uuid.UUID, body: PlayerFields, ctx: Context = Depends(get_context)
) -> PlayerDetail:
    result: PlayerDetail = bus.send(UpdatePlayer(player_id=player_id, **body.model_dump()), ctx)
    return result
