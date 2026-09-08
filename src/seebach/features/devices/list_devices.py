"""Devices admitted to a tournament, with enough to decide which to revoke."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from seebach.platform.bus import bus
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Context, Query
from seebach.shared.models import Device

router = APIRouter(prefix="/tournaments", tags=["devices"])


class DeviceSummary(BaseModel):
    id: uuid.UUID
    label: str
    issued_at: datetime
    revoked_at: datetime | None
    last_seen_at: datetime | None
    active: bool


class ListDevices(Query):
    access = Access.ARBITER

    tournament_id: uuid.UUID


@bus.register(ListDevices)
def handle(query: ListDevices, ctx: Context) -> list[DeviceSummary]:
    devices = ctx.session.scalars(
        select(Device)
        .where(Device.tournament_id == query.tournament_id)
        .order_by(Device.issued_at.desc())
    ).all()
    return [
        DeviceSummary(
            id=device.id,
            label=device.label,
            issued_at=device.issued_at,
            revoked_at=device.revoked_at,
            last_seen_at=device.last_seen_at,
            active=device.revoked_at is None,
        )
        for device in devices
    ]


@router.get("/{tournament_id}/devices", response_model=list[DeviceSummary])
def list_devices(
    tournament_id: uuid.UUID, ctx: Context = Depends(get_context)
) -> list[DeviceSummary]:
    result: list[DeviceSummary] = bus.send(ListDevices(tournament_id=tournament_id), ctx)
    return result
