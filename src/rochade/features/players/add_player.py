"""Enter a player into a section Rochade pairs itself.

Before round 1 the start rank is provisional: the seeding at the first
pairing orders the whole list by rating. After that the list is final and a
new player is a late entry: they take the next number, sit out the rounds
already played, and are paired from the next one.

The name is the player's identity on every board and in the audit log, so
two players in one section may not share one. Add an initial, a club, a year
-- anything that tells them apart on the wall.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.pairing.pair_round import lock_section
from rochade.features.players.list_players import (
    PlayerDetail,
    editable_section,
    player_detail,
    same_name,
)
from rochade.features.scoping import tournament_of_section
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction
from rochade.shared.models import SectionPlayer

router = APIRouter(prefix="/sections", tags=["players"])


#: The widest a name can be on a TRF line, and so on a board here.
NAME_WIDTH = 33
#: More than a hall holds; the TRF starting rank has four digits.
MAX_PLAYERS = 2000


def _clean(value: str) -> str:
    """One line, single spaces, no control characters."""
    return " ".join("".join(c for c in value if c.isprintable()).split())


class PlayerFields(BaseModel):
    """What a player line carries, validated to the TRF column grammar.

    The engine reads fixed columns and `int()`s the numeric ones, so a FIDE
    id with a letter in it or a title that is not a title would make it
    refuse the whole section -- at release, hours after the typo.
    """

    name: str = Field(min_length=1, max_length=NAME_WIDTH)
    #: A FIDE title, or nothing.
    title: str = Field(default="", pattern=r"^(?i:GM|IM|WGM|FM|WIM|CM|WFM|WCM)?$")
    rating: int | None = Field(default=None, ge=0, le=4000)
    #: Three letters, or nothing.
    federation: str = Field(default="", pattern=r"^[A-Za-z]{0,3}$")
    #: Digits only; up to eleven fit the column.
    fide_id: str = Field(default="", pattern=r"^[0-9]{0,11}$")
    #: "m", "w" or "" -- the TRF letter, if the arbiter fills it in.
    sex: str = Field(default="", pattern=r"^(?i:m|w|f)?$")
    #: YYYY/MM/DD, or "".
    birth_date: str = Field(default="", pattern=r"^([0-9]{4}/[0-9]{2}/[0-9]{2})?$")

    @field_validator("name", "title", "federation", "fide_id", "sex", "birth_date", mode="before")
    @classmethod
    def _trimmed(cls, value: object) -> object:
        return _clean(value) if isinstance(value, str) else value

    @field_validator("rating", mode="before")
    @classmethod
    def _zero_is_unrated(cls, value: object) -> object:
        return None if value in (0, "", "0") else value


class AddPlayer(PlayerFields, Command):
    access = Access.ARBITER
    result_model = PlayerDetail

    section_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_section(session, self.section_id)


@bus.register(AddPlayer)
def handle(command: AddPlayer, ctx: Context) -> PlayerDetail:
    section = editable_section(ctx, command.section_id)
    # The section row, so two arbiters entering players at once cannot both
    # take the same next number.
    lock_section(ctx, section.id)
    ctx.session.refresh(section)
    if len(section.players) >= MAX_PLAYERS:
        raise Conflict(f"a section holds at most {MAX_PLAYERS} players", limit=MAX_PLAYERS)
    clash = next((p for p in section.players if same_name(p.name, command.name)), None)
    if clash is not None:
        raise Conflict(
            "a player with this name is already in the section",
            name=clash.name,
            start_rank=clash.start_rank,
        )

    player = SectionPlayer(
        section_id=section.id,
        start_rank=max((p.start_rank for p in section.players), default=0) + 1,
        name=command.name,
        title=command.title.upper(),
        rating=command.rating,
        federation=command.federation.upper(),
        fide_id=command.fide_id,
        sex=command.sex.lower().replace("f", "w"),
        birth_date=command.birth_date,
    )
    section.players.append(player)
    ctx.session.flush()

    rounds_held = max((r.number for r in section.rounds), default=0)
    record(
        ctx,
        section_id=section.id,
        round_number=rounds_held,
        action=EventAction.PLAYER_ADDED,
        start_rank=player.start_rank,
        name=player.name,
        rating=player.rating,
        late_entry=rounds_held > 0,
    )
    return player_detail(player)


@router.post("/{section_id}/players", response_model=PlayerDetail, status_code=201)
def add_player(
    section_id: uuid.UUID, body: PlayerFields, ctx: Context = Depends(get_context)
) -> PlayerDetail:
    result: PlayerDetail = bus.send(AddPlayer(section_id=section_id, **body.model_dump()), ctx)
    return result
