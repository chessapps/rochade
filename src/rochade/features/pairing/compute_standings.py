"""The table of a section Rochade pairs itself, from the engine.

Runs at every release, and again whenever the arbiter corrects a released
board, so the standings shown are always the standings of the results held.
It waits until every board of the rounds it counts has a confirmed result:
a table with a board missing is not a table, and a forced release is
exactly the moment an arbiter would read one.

The table is a derived view. When the engine cannot produce it -- a broken
install, a hang -- the release and the correction still go through, and the
outcome says why the table did not move. Only the explicit "recompute"
command (`ComputeStandings`) turns that into an error the arbiter sees.

`compute_standings` is the function the hooks call; `restand` is the hook
itself; `ComputeStandings` is the same thing as a command.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.locking import lock_round
from rochade.features.pairing.trf_of import trf_for_engine
from rochade.features.scoping import tournament_of_section
from rochade.features.standings.get_standings import SectionStandings, standings_of
from rochade.gacrux import DEFAULT_TIEBREAKS, EngineError, standings, validate_tiebreaks
from rochade.interchange import native_of
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, NotFound, Unavailable, ValidationFailed
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction, ResultState, RoundState
from rochade.shared.models import Round, Section

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sections", tags=["pairing"])


@dataclass(frozen=True)
class StandingsOutcome:
    computed: bool
    after_round: int
    reason: str = ""
    #: The engine failed, as opposed to the table merely not being due yet.
    failed: EngineError | None = None


def compute_standings(ctx: Context, section: Section, after_round: int) -> StandingsOutcome:
    """Rank the section on rounds 1..`after_round`, if they are all in.

    Never raises for an engine failure: the outcome carries it. The caller
    decides whether that is an error (the recompute button) or a note (a
    release, a correction).
    """
    if after_round < 1:
        return StandingsOutcome(False, 0, "no round has been played yet")
    counted = [r for r in section.rounds if r.number <= after_round]
    missing = sorted(
        (r.number, g.board)
        for r in counted
        for g in r.games
        if g.state is not ResultState.CONFIRMED
    )
    if missing:
        where = ", ".join(f"round {r} board {b}" for r, b in missing[:6])
        more = f" and {len(missing) - 6} more" if len(missing) > 6 else ""
        return StandingsOutcome(
            False, after_round, f"boards without a confirmed result: {where}{more}"
        )

    try:
        spec = validate_tiebreaks(section.tiebreak_names or DEFAULT_TIEBREAKS)
    except ValueError as exc:
        return StandingsOutcome(
            False, after_round, f"the section's tie-breaks are not usable: {exc}"
        )

    try:
        rows = standings(
            trf_for_engine(section, upto_round=after_round),
            tiebreaks=spec,
            after_round=after_round,
        )
    except EngineError as exc:
        log.warning("standings for section %s not computed: %s", section.id, exc.message)
        return StandingsOutcome(
            False, after_round, f"the tie-break engine failed: {exc.message}", failed=exc
        )

    by_rank = {p.start_rank: p for p in section.players}
    for row in rows:
        player = by_rank.get(row.start_rank)
        if player is None:  # pragma: no cover - the engine only knows the players we sent
            continue
        player.points = row.points
        player.tiebreaks = list(row.tiebreaks)
        player.rank = row.rank
    section.standings_after_round = after_round
    ctx.session.flush()

    record(
        ctx,
        section_id=section.id,
        round_number=after_round,
        action=EventAction.STANDINGS_COMPUTED,
        tiebreaks=spec,
        players=len(rows),
    )
    return StandingsOutcome(True, after_round)


def restand(ctx: Context, round_: Round) -> StandingsOutcome | None:
    """After a correction: keep the table current for a released native round.

    An open round is not in the table yet, and a manager's section has no
    table of ours to keep; both return None without touching anything. The
    caller holds the round's row lock already; rounds are locked before
    sections everywhere (see `pair_round`), so touching the section here
    cannot deadlock a pairing.
    """
    if round_.state is not RoundState.CONFIRMED or not native_of(round_.section.manager):
        return None
    return compute_standings(ctx, round_.section, round_.number)


def released_round(section: Section) -> int:
    """The newest round whose results are final: released or closed."""
    return max(
        (r.number for r in section.rounds if r.state is not RoundState.OPEN),
        default=0,
    )


def engine_failure(exc: EngineError, what: str) -> Exception:
    """The HTTP shape of an engine failure: ours is a 503, the engine's verdict a 422."""
    if exc.ours:
        return Unavailable(f"{what}: {exc.message}")
    return ValidationFailed(f"{what}: {exc.message}", engine_errors=exc.errors)


# --- the command ------------------------------------------------------------


class ComputeStandingsResult(BaseModel):
    computed: bool
    after_round: int
    reason: str
    standings: SectionStandings


class ComputeStandings(Command):
    access = Access.ARBITER
    result_model = ComputeStandingsResult

    section_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_section(session, self.section_id)


@bus.register(ComputeStandings)
def handle(command: ComputeStandings, ctx: Context) -> ComputeStandingsResult:
    section = ctx.session.get(Section, command.section_id)
    if section is None:
        raise NotFound("section not found", section_id=str(command.section_id))
    if not native_of(section.manager):
        raise Conflict(
            "this section's standings come from its pairing program",
            manager=section.manager,
        )
    # Lock the round the table stands on, so a correction landing at the same
    # moment is serialised with this rather than overwritten by a stale table.
    after = released_round(section)
    newest = next((r for r in section.rounds if r.number == after), None)
    if newest is not None:
        lock_round(ctx, newest.id)
        ctx.session.refresh(section)
    outcome = compute_standings(ctx, section, after)
    if outcome.failed is not None:
        raise engine_failure(outcome.failed, "the tie-break engine could not rank the section")
    return ComputeStandingsResult(
        computed=outcome.computed,
        after_round=outcome.after_round,
        reason=outcome.reason,
        standings=standings_of(section),
    )


@router.post("/{section_id}/standings", response_model=ComputeStandingsResult)
def recompute_standings(
    section_id: uuid.UUID, ctx: Context = Depends(get_context)
) -> ComputeStandingsResult:
    result: ComputeStandingsResult = bus.send(ComputeStandings(section_id=section_id), ctx)
    return result
