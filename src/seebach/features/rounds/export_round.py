"""Write the round's results back into a TRF for Vega, and freeze the round.

The file we emit is the file we imported, with the result cells of this round
patched. Nothing is rebuilt, so every field Vega wrote that we never modelled
goes back to Vega unchanged.

Freezing is the divergence guard. During a round we own the results; between
rounds Vega owns the pairings. Without the freeze, an arbiter can edit a result
in Vega while a player edits it here and neither system can say which is right.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from seebach.features.audit import record
from seebach.features.locking import lock_round
from seebach.features.scoping import tournament_of_round
from seebach.interchange import InterchangeError, ResultEntry, UnknownManager, manager_for
from seebach.platform.bus import bus
from seebach.platform.errors import Conflict, ValidationFailed
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import EventAction, ResultState, RoundState
from seebach.shared.models import Round

router = APIRouter(prefix="/rounds", tags=["arbiter"])


class ExportRoundResult(BaseModel):
    round_id: uuid.UUID
    round_number: int
    filename: str
    content: str
    #: Which adapter produced it, and in what format. Both are worth recording:
    #: the arbiter has to know which program this file is for.
    manager: str
    file_format: str
    boards_written: int
    boards_left_blank: list[int] = Field(default_factory=list)
    forced: bool


class ExportRound(Command):
    access = Access.ARBITER
    result_model = ExportRoundResult

    round_id: uuid.UUID
    #: Export a round that still has unconfirmed boards. Logged as forced.
    force: bool = False

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_round(session, self.round_id)


@bus.register(ExportRound)
def handle(command: ExportRound, ctx: Context) -> ExportRoundResult:
    round_ = lock_round(ctx, command.round_id)

    if round_.state is RoundState.EXPORTED:
        raise Conflict(
            "this round has already been exported",
            round_number=round_.number,
            exported_at=round_.exported_at.isoformat() if round_.exported_at else None,
        )
    if round_.state is not RoundState.CONFIRMED and not command.force:
        raise Conflict(
            "the arbiter has not released this round yet",
            round_number=round_.number,
            state=round_.state.value,
        )

    unconfirmed = [g.board for g in round_.games if g.state is not ResultState.CONFIRMED]
    if unconfirmed and not command.force:
        raise Conflict("some boards are not confirmed", boards=unconfirmed)

    if not round_.source_trf:
        raise ValidationFailed(
            "this round has no source file to write back into",
            round_number=round_.number,
        )

    try:
        manager = manager_for(round_.section.manager)
    except UnknownManager as exc:  # pragma: no cover - written by import
        raise ValidationFailed(str(exc), manager=round_.section.manager) from exc

    results: list[ResultEntry] = []
    blank: list[int] = []
    for game in sorted(round_.games, key=lambda g: g.board):
        if game.state is not ResultState.CONFIRMED or game.white_result == " ":
            blank.append(game.board)
            continue
        results.append(ResultEntry(white_rank=game.white_rank, white_result=game.white_result))

    dropped = manager.capabilities.drops([entry.white_result for entry in results])
    if dropped and not command.force:
        raise Conflict(
            f"{manager.label} cannot carry these result codes, so exporting would "
            "silently change them",
            codes=dropped,
        )

    try:
        emitted = manager.write_results(
            manager.read_round(round_.source_trf), round_.number, results, stem=_stem(round_)
        )
    except InterchangeError as exc:  # pragma: no cover - it parsed on import
        raise ValidationFailed(f"the stored source file no longer reads: {exc}") from exc

    written = len(results)

    round_.state = RoundState.EXPORTED
    round_.exported_at = datetime.now(UTC)

    record(
        ctx,
        section_id=round_.section_id,
        round_number=round_.number,
        action=EventAction.ROUND_EXPORTED,
        filename=emitted.filename,
        manager=manager.key,
        file_format=manager.capabilities.writes_format,
        boards_written=written,
        boards_left_blank=blank,
        forced=command.force,
    )

    return ExportRoundResult(
        round_id=round_.id,
        round_number=round_.number,
        filename=emitted.filename,
        content=emitted.content,
        manager=manager.key,
        file_format=manager.capabilities.writes_format,
        boards_written=written,
        boards_left_blank=blank,
        forced=command.force,
    )


def _stem(round_: Round) -> str:
    """The filename without an extension -- the adapter picks that."""
    section = re.sub(r"[^A-Za-z0-9_-]+", "-", round_.section.name).strip("-") or "section"
    return f"{section}-round{round_.number}"


class ExportBody(BaseModel):
    force: bool = False


@router.post("/{round_id}/export", response_model=ExportRoundResult)
def export_round(
    round_id: uuid.UUID, body: ExportBody, ctx: Context = Depends(get_context)
) -> ExportRoundResult:
    result: ExportRoundResult = bus.send(ExportRound(round_id=round_id, **body.model_dump()), ctx)
    return result
