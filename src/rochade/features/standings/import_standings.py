"""Bring the manager's standings in on their own.

The round import takes them along whenever the player list is part of the
hand-over. This is for the moments without a new round to import: after the
last round, or when the arbiter wants the table refreshed before the next
pairing. It reads the same player list, matches on the start number, and
touches nothing but points, tiebreaks and ranks.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.standings.get_standings import SectionStandings, standings_of
from rochade.interchange.formats.swiss_manager_text import split_blocks
from rochade.platform.bus import bus
from rochade.platform.errors import NotFound, ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction, RoundState
from rochade.shared.models import Section
from rochade.swiss_manager.player_file import PlayerFileError, parse_player_file

router = APIRouter(prefix="/tournaments", tags=["standings"])


class ImportStandingsResult(BaseModel):
    section_name: str
    after_round: int
    players_updated: int
    #: Start numbers in the file that the section does not hold. Nothing is
    #: added for them: the round import owns the player list.
    unknown_start_numbers: list[int] = Field(default_factory=list)
    standings: SectionStandings


class ImportStandings(Command):
    access = Access.ARBITER
    result_model = ImportStandingsResult

    tournament_id: uuid.UUID
    section_name: str = Field(min_length=1, max_length=120)
    #: The manager's player list export, as a file.
    content: str = Field(min_length=1)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return self.tournament_id


@bus.register(ImportStandings)
def handle(command: ImportStandings, ctx: Context) -> ImportStandingsResult:
    section = ctx.session.scalar(
        select(Section).where(
            Section.tournament_id == command.tournament_id,
            Section.name == command.section_name,
        )
    )
    if section is None:
        raise NotFound(
            "no such section; import its first round before its standings",
            section_name=command.section_name,
        )

    players_text, _pairings = split_blocks(command.content)
    if players_text is None:
        raise ValidationFailed(
            "this is not the player list; standings come with Spielerdaten "
            "(Extras → Daten Import/Export → Spielerdaten (Text-File))"
        )
    try:
        lines = parse_player_file(players_text)
    except PlayerFileError as exc:
        raise ValidationFailed(f"player file: {exc}", line_no=exc.line_no) from exc
    if not any(line.rank is not None for line in lines):
        raise ValidationFailed("the player list carries no standings (no Rang column)")

    held = {p.start_rank: p for p in section.players}
    updated = 0
    unknown: list[int] = []
    for line in lines:
        player = held.get(line.start_number)
        if player is None:
            unknown.append(line.start_number)
            continue
        player.points = line.points
        player.tiebreaks = list(line.tiebreaks)
        player.rank = line.rank
        updated += 1

    # Current for the last round whose results went back to the manager.
    after = max((r.number for r in section.rounds if r.state is RoundState.EXPORTED), default=0)
    section.standings_after_round = after
    ctx.session.flush()

    record(
        ctx,
        section_id=section.id,
        round_number=after,
        action=EventAction.STANDINGS_IMPORTED,
        players_updated=updated,
        unknown_start_numbers=unknown,
    )

    return ImportStandingsResult(
        section_name=section.name,
        after_round=after,
        players_updated=updated,
        unknown_start_numbers=sorted(unknown),
        standings=standings_of(section),
    )


class ImportStandingsBody(BaseModel):
    section_name: str
    content: str


@router.post("/{tournament_id}/standings", response_model=ImportStandingsResult, status_code=201)
def import_standings(
    tournament_id: uuid.UUID, body: ImportStandingsBody, ctx: Context = Depends(get_context)
) -> ImportStandingsResult:
    result: ImportStandingsResult = bus.send(
        ImportStandings(tournament_id=tournament_id, **body.model_dump()), ctx
    )
    return result
