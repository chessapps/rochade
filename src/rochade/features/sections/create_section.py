"""Open a section in a tournament Rochade pairs itself.

For a manager's tournament a section is born from its first import and the
file says everything about it. Here nothing arrives from anywhere, so the
arbiter says the three things the engine needs before it can pair round 1:
how many rounds, which tie-breaks decide the table, and who has white on
board one. The colour is drawn by lot right here when the arbiter leaves it
open, so that the pairing preview and the pairing it commits are the same.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from rochade.features.audit import record
from rochade.gacrux import DEFAULT_TIEBREAKS, validate_tiebreaks
from rochade.interchange import native_of
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, NotFound, ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction
from rochade.shared.models import Section, Tournament

router = APIRouter(prefix="/tournaments", tags=["sections"])

Colour = Literal["white", "black"]


class CreateSectionResult(BaseModel):
    section_id: uuid.UUID
    name: str
    declared_rounds: int
    tiebreaks: list[str]
    top_board_colour: str
    drawn_by_lot: bool


class CreateSection(Command):
    access = Access.ARBITER
    result_model = CreateSectionResult

    tournament_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    declared_rounds: int = Field(ge=1, le=30)
    #: Engine tie-break codes, `PTS` first. See `rochade.gacrux.tiebreaks`.
    tiebreaks: list[str] = Field(default_factory=lambda: list(DEFAULT_TIEBREAKS))
    #: Who has white on board one in round 1. None draws lots.
    top_board_colour: Colour | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _one_line(cls, value: object) -> object:
        # It lands on a TRF header line and in every board's label.
        if isinstance(value, str):
            return " ".join("".join(c for c in value if c.isprintable()).split())
        return value

    def check(self) -> None:
        try:
            validate_tiebreaks(self.tiebreaks)
        except ValueError as exc:
            raise ValidationFailed(str(exc), tiebreaks=self.tiebreaks) from exc


@bus.register(CreateSection)
def handle(command: CreateSection, ctx: Context) -> CreateSectionResult:
    tournament = ctx.session.get(Tournament, command.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(command.tournament_id))
    if not native_of(tournament.manager):
        raise Conflict(
            "this tournament is run by its pairing program; sections arrive with its first export",
            manager=tournament.manager,
        )
    name = command.name.strip()
    taken = ctx.session.scalar(
        select(Section.id).where(Section.tournament_id == tournament.id, Section.name == name)
    )
    if taken is not None:
        raise Conflict("a section with this name already exists", section_name=name)

    drawn = command.top_board_colour is None
    colour: str = command.top_board_colour or secrets.choice(("white", "black"))
    tiebreaks = validate_tiebreaks(command.tiebreaks)

    section = Section(
        tournament_id=tournament.id,
        name=name,
        manager=tournament.manager,
        declared_rounds=command.declared_rounds,
        tiebreak_names=tiebreaks,
        top_board_colour=colour,
    )
    ctx.session.add(section)
    ctx.session.flush()

    record(
        ctx,
        section_id=section.id,
        round_number=0,
        action=EventAction.SECTION_CREATED,
        name=name,
        declared_rounds=command.declared_rounds,
        tiebreaks=tiebreaks,
        top_board_colour=colour,
        drawn_by_lot=drawn,
    )
    return CreateSectionResult(
        section_id=section.id,
        name=section.name,
        declared_rounds=command.declared_rounds,
        tiebreaks=tiebreaks,
        top_board_colour=colour,
        drawn_by_lot=drawn,
    )


class CreateSectionBody(BaseModel):
    name: str
    declared_rounds: int
    tiebreaks: list[str] = Field(default_factory=lambda: list(DEFAULT_TIEBREAKS))
    top_board_colour: Colour | None = None


@router.post("/{tournament_id}/sections", response_model=CreateSectionResult, status_code=201)
def create_section(
    tournament_id: uuid.UUID, body: CreateSectionBody, ctx: Context = Depends(get_context)
) -> CreateSectionResult:
    result: CreateSectionResult = bus.send(
        CreateSection(tournament_id=tournament_id, **body.model_dump()), ctx
    )
    return result
