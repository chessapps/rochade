"""The section's player list, for the desk.

One shape for every tournament. Whether the list can be edited here is a
fact about the program: a manager's list is rebuilt from its next export, so
editing it would be undone within the hour; a section Rochade pairs itself
has no other list. The response says which, so the screen need not guess.

The small helpers below are what the other player use cases share: which
section, whether it may be edited, and how a row is described.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rochade.features.scoping import tournament_of_section
from rochade.interchange import native_of
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Context, Query
from rochade.shared.models import Section, SectionPlayer

router = APIRouter(prefix="/sections", tags=["players"])


class PlayerDetail(BaseModel):
    id: uuid.UUID
    start_rank: int
    name: str
    title: str
    rating: int | None
    federation: str
    fide_id: str
    sex: str
    birth_date: str
    #: The round from which the player is no longer paired; None while in.
    withdrawn_from_round: int | None
    points: float | None
    rank: int | None


class PlayerList(BaseModel):
    section_id: uuid.UUID
    section_name: str
    #: Players may be added, edited and withdrawn here.
    editable: bool
    #: Round 1 has been paired, so the start ranks are final and a new
    #: player is a late entry.
    seeded: bool
    rounds_held: int
    players: list[PlayerDetail]


class ListPlayers(Query):
    access = Access.STAFF

    section_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_section(session, self.section_id)


@bus.register(ListPlayers)
def handle(query: ListPlayers, ctx: Context) -> PlayerList:
    section = ctx.session.get(Section, query.section_id)
    if section is None:
        raise NotFound("section not found", section_id=str(query.section_id))
    return player_list(section)


def player_list(section: Section) -> PlayerList:
    return PlayerList(
        section_id=section.id,
        section_name=section.name,
        editable=native_of(section.manager),
        seeded=bool(section.rounds),
        rounds_held=max((r.number for r in section.rounds), default=0),
        players=[player_detail(p) for p in sorted(section.players, key=lambda p: p.start_rank)],
    )


def player_detail(player: SectionPlayer) -> PlayerDetail:
    return PlayerDetail(
        id=player.id,
        start_rank=player.start_rank,
        name=player.name,
        title=player.title,
        rating=player.rating,
        federation=player.federation,
        fide_id=player.fide_id,
        sex=player.sex,
        birth_date=player.birth_date,
        withdrawn_from_round=player.withdrawn_from_round,
        points=player.points,
        rank=player.rank,
    )


def editable_section(ctx: Context, section_id: uuid.UUID) -> Section:
    """The section, or the reason its list cannot be touched here."""
    section = ctx.session.get(Section, section_id)
    if section is None:
        raise NotFound("section not found", section_id=str(section_id))
    if not native_of(section.manager):
        raise Conflict(
            "this section's players come from its pairing program; "
            "import its next export to change them",
            manager=section.manager,
        )
    return section


def same_name(a: str, b: str) -> bool:
    return " ".join(a.casefold().split()) == " ".join(b.casefold().split())


@router.get("/{section_id}/players", response_model=PlayerList)
def list_players(section_id: uuid.UUID, ctx: Context = Depends(get_context)) -> PlayerList:
    result: PlayerList = bus.send(ListPlayers(section_id=section_id), ctx)
    return result
