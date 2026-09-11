"""Write the round's results back in whatever the section's manager takes, and freeze it.

The adapter decides the file: Vega gets the TRF we imported with this round's
result cells patched, Swiss-Manager gets its own pairing file. What the
manager wrote and we never modelled goes back unchanged -- with one
exception. A round that came in as the pairing list alone has a source that
knows nothing of the rounds before it, and Vega's import replaces the whole
tournament with the file, so such a source is rebuilt from what Rochade holds
before the results go in. Seen the hard way on 2026-09-11: a round-2 export
without round 1 wiped round 1 in Vega.

Freezing is the divergence guard. During a round we own the results; between
rounds the manager owns the pairings. Without the freeze, an arbiter can edit a
result there while a player edits it here and neither system can say which is
right.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.locking import lock_round
from rochade.features.pairing.trf_of import build_document
from rochade.features.roster import roster_of
from rochade.features.scoping import tournament_of_round
from rochade.interchange import (
    InterchangeError,
    Manager,
    ResultEntry,
    RoundDocument,
    UnknownManager,
    manager_for,
)
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, NotFound, ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context, Query
from rochade.shared.enums import EventAction, ResultState, RoundState
from rochade.shared.models import Round
from rochade.trf import Colour, RoundEntry
from rochade.trf.build import build

router = APIRouter(prefix="/rounds", tags=["arbiter"])


class ExportRoundResult(BaseModel):
    round_id: uuid.UUID
    round_number: int
    filename: str
    content: str
    #: Which adapter produced it, and in what format. Both are worth recording:
    #: the arbiter has to know which program this file is for.
    manager: str
    manager_label: str
    file_format: str
    #: What the arbiter does with the file, in the manager's own menu terms.
    next_step: str
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


@dataclass(frozen=True)
class Rendered:
    """The file for one round, and what went into it."""

    filename: str
    content: str
    manager: Manager
    written: int
    blank: list[int]


def render(round_: Round, *, force: bool) -> Rendered:
    """Write the round's confirmed results into its source document.

    Pure over the round's rows: the export command calls it once and freezes
    the round, and the re-download reads it again later -- the round is frozen
    by then, so the file comes out the same.
    """
    if not round_.source_trf:
        raise ValidationFailed(
            "this round has no source file to write back into",
            round_number=round_.number,
        )

    try:
        manager = manager_for(round_.section.manager)
    except UnknownManager as exc:  # pragma: no cover - written by import
        raise ValidationFailed(str(exc), manager=round_.section.manager) from exc
    if manager.capabilities.native:
        raise Conflict(
            "this section is paired in Rochade; there is no file to export",
            round_number=round_.number,
        )

    # The source may be the pairings alone, named from the roster we hold; the
    # roster is the one that import saw, since the next round cannot come in
    # before this one goes out.
    try:
        document = manager.read_round(round_.source_trf, roster_of(round_.section))
    except InterchangeError as exc:  # pragma: no cover - it parsed on import
        raise ValidationFailed(f"the stored source file no longer reads: {exc}") from exc
    if document.declared_rounds is None and round_.section.declared_rounds is not None:
        # Vega's folder files carry no round count; the section remembers the
        # one the arbiter gave at import, and the file we hand back needs it.
        document = replace(document, declared_rounds=round_.section.declared_rounds)
    document = _with_history(document, round_)

    # What the manager already knows. A bye it allocated, or a result it exported
    # with the round, is not something we write -- it goes back as it came, so it
    # is neither counted nor checked against what the manager can carry.
    before = {
        row.white_rank: (row.white_result, row.black_result)
        for row in document.board_rows(round_.number)
    }

    results: list[ResultEntry] = []
    blank: list[int] = []
    for game in sorted(round_.games, key=lambda g: g.board):
        if game.state is not ResultState.CONFIRMED or game.white_result == " ":
            blank.append(game.board)
            continue
        if before.get(game.white_rank) == (game.white_result, game.black_result):
            continue
        results.append(
            ResultEntry(
                white_rank=game.white_rank,
                white_result=game.white_result,
                black_result=game.black_result,
            )
        )

    dropped = manager.capabilities.drops(
        [code for entry in results for code in (entry.white_result, entry.black_result)]
    )
    if dropped and not force:
        raise Conflict(
            f"{manager.label} cannot carry these result codes, so exporting would "
            "silently change them",
            codes=dropped,
        )

    try:
        emitted = manager.write_results(document, round_.number, results, stem=_stem(round_))
    except InterchangeError as exc:
        raise ValidationFailed(f"{manager.label} cannot write this round: {exc}") from exc

    return Rendered(emitted.filename, emitted.content, manager, len(results), blank)


def _with_history(document: RoundDocument, round_: Round) -> RoundDocument:
    """The stored source, or one rebuilt from the section when it is missing
    results of earlier rounds that Rochade holds.

    A pairing list alone (Vega's SortedPairs.txt, Swiss-Manager's Auslosung)
    names the round and nothing before it, so the TRF built from it has blank
    earlier rounds. A real TRF from the manager carries its history and is
    left exactly as it came.
    """
    section = round_.section
    earlier = [r for r in section.rounds if r.number < round_.number]
    if not earlier:
        return document

    def played(r: Round) -> bool:
        return any(g.white_result != " " for g in r.games)

    def carried(r: Round) -> bool:
        return any(row.white_result != " " for row in document.pairings.get(r.number, []))

    if all(carried(r) for r in earlier if played(r)):
        return document

    built = build_document(section, upto_round=round_.number - 1)
    entries = {p.start_rank: dict(p.rounds) for p in built.players}
    for row in document.pairings.get(round_.number, []):
        if row.black_rank is None:
            entries[row.white_rank][round_.number] = RoundEntry(
                round_.number, None, Colour.NONE, row.white_result
            )
            continue
        entries[row.white_rank][round_.number] = RoundEntry(
            round_.number, row.black_rank, Colour.WHITE, row.white_result
        )
        entries[row.black_rank][round_.number] = RoundEntry(
            round_.number, row.white_rank, Colour.BLACK, row.black_result
        )
    rebuilt = replace(
        built,
        name=document.tournament_name or built.name,
        declared_rounds=document.declared_rounds or built.declared_rounds,
        players=[replace(p, rounds=entries[p.start_rank]) for p in built.players],
    )
    return replace(document, source=build(rebuilt))


def _result(round_: Round, rendered: Rendered, *, forced: bool) -> ExportRoundResult:
    return ExportRoundResult(
        round_id=round_.id,
        round_number=round_.number,
        filename=rendered.filename,
        content=rendered.content,
        manager=rendered.manager.key,
        manager_label=rendered.manager.label,
        file_format=rendered.manager.capabilities.writes_format,
        next_step=rendered.manager.capabilities.import_howto,
        boards_written=rendered.written,
        boards_left_blank=rendered.blank,
        forced=forced,
    )


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

    rendered = render(round_, force=command.force)
    manager, written, blank = rendered.manager, rendered.written, rendered.blank

    round_.state = RoundState.EXPORTED
    round_.exported_at = datetime.now(UTC)

    record(
        ctx,
        section_id=round_.section_id,
        round_number=round_.number,
        action=EventAction.ROUND_EXPORTED,
        filename=rendered.filename,
        manager=manager.key,
        file_format=manager.capabilities.writes_format,
        boards_written=written,
        boards_left_blank=blank,
        forced=command.force,
    )

    return _result(round_, rendered, forced=command.force)


class GetExportFile(Query):
    """The file again, for a round already exported.

    A download lost between the browser and the manager is otherwise the end of
    the round: the export cannot run twice. The round is frozen, so rendering it
    again yields the same file.
    """

    access = Access.ARBITER

    round_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_round(session, self.round_id)


@bus.register(GetExportFile)
def handle_get(query: GetExportFile, ctx: Context) -> ExportRoundResult:
    round_ = ctx.session.get(Round, query.round_id)
    if round_ is None:
        raise NotFound("round not found", round_id=str(query.round_id))
    if round_.state is not RoundState.EXPORTED:
        raise Conflict(
            "this round has not been exported yet",
            round_number=round_.number,
            state=round_.state.value,
        )
    forced = any(g.state is not ResultState.CONFIRMED for g in round_.games)
    return _result(round_, render(round_, force=True), forced=forced)


def _stem(round_: Round) -> str:
    """The section's name made file-safe. The adapter adds the round and the extension."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", round_.section.name).strip("-") or "section"


class ExportBody(BaseModel):
    force: bool = False


@router.post("/{round_id}/export", response_model=ExportRoundResult)
def export_round(
    round_id: uuid.UUID, body: ExportBody, ctx: Context = Depends(get_context)
) -> ExportRoundResult:
    result: ExportRoundResult = bus.send(ExportRound(round_id=round_id, **body.model_dump()), ctx)
    return result


@router.get("/{round_id}/export", response_model=ExportRoundResult)
def get_export_file(round_id: uuid.UUID, ctx: Context = Depends(get_context)) -> ExportRoundResult:
    result: ExportRoundResult = bus.send(GetExportFile(round_id=round_id), ctx)
    return result
