"""Take a pairing back.

Only the newest round, only while nobody has entered anything on it: a
board with a claim on it is a game that has been played, or is being, and a
pairing under it is not a mistake to undo. The round before reopens for
corrections, and the next pairing -- the same one, if nothing changed -- is
one click away. Unpairing round 1 leaves no round at all, so the next pairing
seeds the list again, and a player entered in between is seeded with the rest.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rochade.features.audit import record
from rochade.features.locking import lock_round
from rochade.features.pairing.pair_round import lock_section
from rochade.features.scoping import tournament_of_round
from rochade.interchange import native_of
from rochade.platform.bus import bus
from rochade.platform.errors import Conflict
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction, ResultState, RoundState

router = APIRouter(prefix="/rounds", tags=["pairing"])


class UnpairRoundResult(BaseModel):
    section_id: uuid.UUID
    round_number: int
    #: The round reopened for corrections, if there was one.
    previous_round_reopened: int | None


class UnpairRound(Command):
    access = Access.ARBITER
    result_model = UnpairRoundResult

    round_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_round(session, self.round_id)


@bus.register(UnpairRound)
def handle(command: UnpairRound, ctx: Context) -> UnpairRoundResult:
    # The round first, then the section: the one order every native write
    # uses (see `pair_round.lock_section_and_newest_round`).
    round_ = lock_round(ctx, command.round_id)
    section = lock_section(ctx, round_.section_id)
    ctx.session.refresh(section)
    if not native_of(section.manager):
        raise Conflict(
            "this round was imported from the pairing program; re-pair it there",
            manager=section.manager,
        )
    newest = max(section.rounds, key=lambda r: r.number)
    if newest.id != round_.id:
        raise Conflict(
            f"round {round_.number} is not the newest; only round {newest.number} can be unpaired",
            round_number=round_.number,
            newest=newest.number,
        )
    if round_.state is not RoundState.OPEN:
        raise Conflict(
            "this round has been released; its results stand",
            round_number=round_.number,
            state=round_.state.value,
        )
    entered = sorted(
        g.board
        for g in round_.games
        if g.black_rank is not None and g.state is not ResultState.EMPTY
    )
    if entered:
        raise Conflict(
            "results have been entered on this round; a pairing with results on it is not undone",
            boards=entered,
        )

    previous = max(
        (r for r in section.rounds if r.number < round_.number),
        key=lambda r: r.number,
        default=None,
    )
    if previous is not None:
        previous.state = RoundState.CONFIRMED
        previous.exported_at = None

    number = round_.number
    section.rounds.remove(round_)
    ctx.session.flush()

    record(
        ctx,
        section_id=section.id,
        round_number=number,
        action=EventAction.ROUND_UNPAIRED,
        previous_round_reopened=previous.number if previous else None,
    )
    return UnpairRoundResult(
        section_id=section.id,
        round_number=number,
        previous_round_reopened=previous.number if previous else None,
    )


@router.delete("/{round_id}", response_model=UnpairRoundResult)
def unpair_round(round_id: uuid.UUID, ctx: Context = Depends(get_context)) -> UnpairRoundResult:
    result: UnpairRoundResult = bus.send(UnpairRound(round_id=round_id), ctx)
    return result
