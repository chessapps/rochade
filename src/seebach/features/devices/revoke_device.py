"""Kill one device's access.

The reason anonymous claims are acceptable at all: a leaked token is one click
to revoke, and everything it did is reversible and in the audit log.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from seebach.features.audit import record
from seebach.features.scoping import tournament_of_device
from seebach.platform.bus import bus
from seebach.platform.errors import NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import EventAction
from seebach.shared.models import Device

router = APIRouter(prefix="/devices", tags=["devices"])


class RevokeDeviceResult(BaseModel):
    device_id: uuid.UUID
    revoked_at: datetime


class RevokeDevice(Command):
    access = Access.ARBITER
    result_model = RevokeDeviceResult

    device_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_device(session, self.device_id)


@bus.register(RevokeDevice)
def handle(command: RevokeDevice, ctx: Context) -> RevokeDeviceResult:
    device = ctx.session.get(Device, command.device_id)
    if device is None:
        raise NotFound("device not found", device_id=str(command.device_id))

    # Revoking twice is not an error -- the arbiter's intent is already met.
    if device.revoked_at is None:
        device.revoked_at = datetime.now(UTC)
        section_id = next((s.id for s in device.tournament.sections), None)
        if section_id is not None:
            record(
                ctx,
                section_id=section_id,
                round_number=0,
                action=EventAction.DEVICE_REVOKED,
                device=str(device.id),
                label=device.label,
            )

    return RevokeDeviceResult(device_id=device.id, revoked_at=device.revoked_at)


@router.post("/{device_id}/revoke", response_model=RevokeDeviceResult)
def revoke_device(device_id: uuid.UUID, ctx: Context = Depends(get_context)) -> RevokeDeviceResult:
    result: RevokeDeviceResult = bus.send(RevokeDevice(device_id=device_id), ctx)
    return result
