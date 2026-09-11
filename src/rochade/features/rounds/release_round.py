"""The arbiter confirms the round.

This is the gate the whole trust model hangs on: every claim entered on a phone
becomes final here, and nowhere else. Boards nobody claimed and boards still in
dispute block the release, because those are exactly the ones an arbiter must
look at rather than wave through.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.locking import lock_round
from rochade.features.pairing.compute_standings import compute_standings
from rochade.features.scoping import tournament_of_round
from rochade.interchange import native_of
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict, RoundFrozen
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction, ResultState, RoundState

router = APIRouter(prefix="/rounds", tags=["arbiter"])


class ReleaseRoundResult(BaseModel):
    round_id: uuid.UUID
    round_number: int
    state: RoundState
    confirmed: int
    forced: bool
    #: For a section Rochade pairs itself: whether the table was recomputed
    #: on release, and if not, why (boards a forced release left open).
    standings_computed: bool | None = None
    standings_note: str = ""


class ReleaseRound(Command):
    access = Access.ARBITER
    result_model = ReleaseRoundResult

    round_id: uuid.UUID
    #: Confirm the round with boards still empty or disputed. Logged as forced.
    force: bool = False
    note: str = Field(default="", max_length=500)

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_round(session, self.round_id)


@bus.register(ReleaseRound)
def handle(command: ReleaseRound, ctx: Context) -> ReleaseRoundResult:
    round_ = lock_round(ctx, command.round_id)

    if round_.state is RoundState.EXPORTED:
        raise RoundFrozen(
            "this round has been closed (exported, or the next round paired on it) "
            "and is read-only",
            round_number=round_.number,
        )
    if round_.state is RoundState.CONFIRMED:
        raise Conflict("this round has already been released", round_number=round_.number)

    empty = [g.board for g in round_.games if g.state is ResultState.EMPTY]
    disputed = [g.board for g in round_.games if g.state is ResultState.DISPUTED]
    if (empty or disputed) and not command.force:
        raise Conflict(
            "some boards are not ready to be confirmed",
            empty_boards=empty,
            disputed_boards=disputed,
        )

    confirmed = 0
    for game in round_.games:
        if game.state is ResultState.CLAIMED:
            game.state = ResultState.CONFIRMED
            confirmed += 1

    round_.state = RoundState.CONFIRMED
    round_.released_at = datetime.now(UTC)

    # The table is a derived view: an engine that cannot rank the section
    # tonight must not stop the arbiter from closing the round to the phones.
    computed: bool | None = None
    note = ""
    if native_of(round_.section.manager):
        outcome = compute_standings(ctx, round_.section, round_.number)
        computed, note = outcome.computed, outcome.reason

    record(
        ctx,
        section_id=round_.section_id,
        round_number=round_.number,
        action=EventAction.ROUND_RELEASED,
        confirmed=confirmed,
        empty_boards=empty,
        disputed_boards=disputed,
        forced=command.force,
        note=command.note,
        standings_computed=computed,
    )

    return ReleaseRoundResult(
        round_id=round_.id,
        round_number=round_.number,
        state=round_.state,
        confirmed=confirmed,
        forced=command.force,
        standings_computed=computed,
        standings_note=note,
    )


class ReleaseBody(BaseModel):
    force: bool = False
    note: str = ""


@router.post("/{round_id}/release", response_model=ReleaseRoundResult)
def release_round(
    round_id: uuid.UUID, body: ReleaseBody, ctx: Context = Depends(get_context)
) -> ReleaseRoundResult:
    result: ReleaseRoundResult = bus.send(ReleaseRound(round_id=round_id, **body.model_dump()), ctx)
    return result
