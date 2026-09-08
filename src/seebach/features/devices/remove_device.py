"""Take a revoked device off the list.

Revoking is what stops a phone; removing only tidies the list afterwards. A
device that still works cannot be removed, because that would be a revoke that
skipped the audit log. The events the device produced stay: they carry its id
in their payload, not a foreign key, exactly so the history survives the row.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from seebach.features.audit import record
from seebach.features.scoping import tournament_of_device
from seebach.platform.bus import bus
from seebach.platform.errors import Conflict, NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import EventAction
from seebach.shared.models import Device

router = APIRouter(prefix="/devices", tags=["devices"])


class RemoveDeviceResult(BaseModel):
    device_id: uuid.UUID


class RemoveDevice(Command):
    access = Access.ARBITER
    result_model = RemoveDeviceResult

    device_id: uuid.UUID

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        return tournament_of_device(session, self.device_id)


@bus.register(RemoveDevice)
def handle(command: RemoveDevice, ctx: Context) -> RemoveDeviceResult:
    device = ctx.session.get(Device, command.device_id)
    if device is None:
        raise NotFound("device not found", device_id=str(command.device_id))
    if device.revoked_at is None:
        raise Conflict("revoke the device first; only a revoked one can be removed")

    section_id = next((s.id for s in device.tournament.sections), None)
    if section_id is not None:
        record(
            ctx,
            section_id=section_id,
            round_number=0,
            action=EventAction.DEVICE_REMOVED,
            device=str(device.id),
            label=device.label,
        )
    ctx.session.delete(device)
    ctx.session.flush()

    return RemoveDeviceResult(device_id=command.device_id)


@router.delete("/{device_id}", response_model=RemoveDeviceResult)
def remove_device(device_id: uuid.UUID, ctx: Context = Depends(get_context)) -> RemoveDeviceResult:
    result: RemoveDeviceResult = bus.send(RemoveDevice(device_id=device_id), ctx)
    return result
