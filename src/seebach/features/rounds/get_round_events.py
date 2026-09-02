"""What happened on each board of a round, newest first.

The audit log is the only way to answer "who entered this": a dispute is two
phones disagreeing, and the arbiter settles it faster knowing which phone said
what, and when. The log is anchored to names rather than game ids, so the
board number is looked up from the round's current pairings; an event for a
pairing that a re-import removed comes back with no board.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.scoping import tournament_of_round
from seebach.platform.bus import bus
from seebach.platform.errors import NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Context, Query
from seebach.shared.enums import EventAction, PrincipalKind
from seebach.shared.models import Device, GameEvent, Round

router = APIRouter(prefix="/rounds", tags=["arbiter"])


class RoundEvent(BaseModel):
    id: uuid.UUID
    board: int | None
    white_name: str | None
    black_name: str | None
    action: EventAction
    actor_kind: PrincipalKind
    #: The label the arbiter gave the phone, when a phone did it.
    device_label: str | None
    at: datetime
    payload: dict[str, Any]


class GetRoundEvents(Query):
    access = Access.STAFF

    round_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_round(session, self.round_id)


@bus.register(GetRoundEvents)
def handle(query: GetRoundEvents, ctx: Context) -> list[RoundEvent]:
    round_ = ctx.session.get(Round, query.round_id)
    if round_ is None:
        raise NotFound("round not found", round_id=str(query.round_id))

    boards = {(g.white_name, g.black_name): g.board for g in round_.games}
    rows = ctx.session.execute(
        select(GameEvent, Device.label)
        .outerjoin(Device, Device.id == GameEvent.device_id)
        .where(GameEvent.section_id == round_.section_id)
        .where(GameEvent.round_number == round_.number)
        .order_by(GameEvent.created_at.desc(), GameEvent.id)
    ).all()

    return [
        RoundEvent(
            id=event.id,
            board=boards.get((event.white_name, event.black_name)),
            white_name=event.white_name,
            black_name=event.black_name,
            action=event.action,
            actor_kind=event.actor_kind,
            device_label=label if event.device_id else None,
            at=event.created_at,
            payload=event.payload,
        )
        for event, label in rows
    ]


@router.get("/{round_id}/events", response_model=list[RoundEvent])
def get_round_events(round_id: uuid.UUID, ctx: Context = Depends(get_context)) -> list[RoundEvent]:
    result: list[RoundEvent] = bus.send(GetRoundEvents(round_id=round_id), ctx)
    return result
