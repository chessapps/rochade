"""Redeem a join code: the phone mints its own device.

Unauthenticated by necessity -- the phone has nothing yet -- and off by
default. `ROCHADE_DEVICE_JOIN_ENABLED` turns it on; the compose stack does,
because that is where a phone that cannot reach a QR code needs a way in.

Every redemption makes its **own** device row rather than handing out a shared
token, so the audit log still says which phone claimed what, and one phone can
be revoked without stranding the hall.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from rochade.features.audit import record
from rochade.features.devices.join_code import normalise
from rochade.platform.auth.tokens import mint
from rochade.platform.bus import bus
from rochade.platform.config import settings
from rochade.platform.errors import NotFound, ValidationFailed
from rochade.platform.http import get_public_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.enums import EventAction
from rochade.shared.models import Device, Tournament

router = APIRouter(prefix="/devices", tags=["devices"])


class JoinedDevice(BaseModel):
    tournament_id: uuid.UUID
    tournament_name: str
    device_id: uuid.UUID
    label: str
    #: Shown once, exactly as the QR payload carries it.
    token: str


class JoinDevice(Command):
    access = Access.PUBLIC
    result_model = JoinedDevice

    code: str = Field(min_length=1, max_length=32)
    label: str = Field(default="", max_length=120)


@bus.register(JoinDevice)
def handle(command: JoinDevice, ctx: Context) -> JoinedDevice:
    if not settings().device_join_enabled:
        raise ValidationFailed(
            "joining with a code is switched off here; scan the QR code the arbiter issued"
        )

    code = normalise(command.code)
    tournament = ctx.session.scalar(select(Tournament).where(Tournament.join_code == code))
    # Deliberately the same answer for "no such code" and "joining is closed for
    # that tournament": a wrong guess learns nothing from the difference.
    if tournament is None or not tournament.join_code:
        raise NotFound("that code does not open anything")

    token, token_hash = mint()
    device = Device(
        tournament_id=tournament.id,
        label=command.label.strip() or f"code {code}",
        token_hash=token_hash,
    )
    ctx.session.add(device)
    ctx.session.flush()

    section_id = next((s.id for s in tournament.sections), None)
    if section_id is not None:
        record(
            ctx,
            section_id=section_id,
            round_number=0,
            action=EventAction.DEVICE_ISSUED,
            device=str(device.id),
            label=device.label,
            joined_with_code=True,
        )

    return JoinedDevice(
        tournament_id=tournament.id,
        tournament_name=tournament.name,
        device_id=device.id,
        label=device.label,
        token=token,
    )


class JoinBody(BaseModel):
    code: str
    label: str = ""


@router.post("/join", response_model=JoinedDevice, status_code=201)
def join_device(body: JoinBody, ctx: Context = Depends(get_public_context)) -> JoinedDevice:
    result: JoinedDevice = bus.send(JoinDevice(**body.model_dump()), ctx)
    return result
