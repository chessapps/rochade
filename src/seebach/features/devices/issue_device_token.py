"""Mint a device token and hand back the QR payload.

App-issued, never through the IdP: the thing being admitted is a phone in a
hall for one playing day, not a person with an account. The token is shown
exactly once, here, because only its hash is stored -- a database read cannot
mint access.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from seebach.features.audit import record
from seebach.platform.auth.tokens import mint
from seebach.platform.bus import bus
from seebach.platform.config import settings
from seebach.platform.errors import NotFound
from seebach.platform.http import get_context
from seebach.platform.mediator import Access, Command, Context
from seebach.shared.enums import EventAction
from seebach.shared.models import Device, Tournament

router = APIRouter(prefix="/tournaments", tags=["devices"])


class IssueDeviceTokenResult(BaseModel):
    device_id: uuid.UUID
    label: str
    #: Shown once. Not recoverable afterwards.
    token: str
    expires_at: datetime
    qr_payload: str


class IssueDeviceToken(Command):
    access = Access.ARBITER
    result_model = IssueDeviceTokenResult

    tournament_id: uuid.UUID
    label: str = Field(default="", max_length=120)
    #: Defaults to the end of the current playing day.
    expires_at: datetime | None = None
    base_url: str = Field(default="", max_length=255)


@bus.register(IssueDeviceToken)
def handle(command: IssueDeviceToken, ctx: Context) -> IssueDeviceTokenResult:
    tournament = ctx.session.get(Tournament, command.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(command.tournament_id))

    token, token_hash = mint()
    expires_at = command.expires_at or datetime.now(UTC) + timedelta(
        hours=settings().device_token_ttl_hours
    )

    device = Device(
        tournament_id=tournament.id,
        label=command.label,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    ctx.session.add(device)
    ctx.session.flush()

    # The audit log is anchored to a section; device events belong to the
    # tournament, so they hang off any of its sections when one exists.
    section_id = next((s.id for s in tournament.sections), None)
    if section_id is not None:
        record(
            ctx,
            section_id=section_id,
            round_number=0,
            action=EventAction.DEVICE_ISSUED,
            device=str(device.id),
            label=device.label,
            expires_at=expires_at.isoformat(),
        )

    return IssueDeviceTokenResult(
        device_id=device.id,
        label=device.label,
        token=token,
        expires_at=expires_at,
        qr_payload=_qr_payload(command.base_url, tournament.id, token),
    )


def _qr_payload(base_url: str, tournament_id: uuid.UUID, token: str) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}/hall/{tournament_id}#t={token}"


class IssueDeviceBody(BaseModel):
    label: str = ""
    expires_at: datetime | None = None
    base_url: str = ""


@router.post("/{tournament_id}/devices", response_model=IssueDeviceTokenResult, status_code=201)
def issue_device_token(
    tournament_id: uuid.UUID, body: IssueDeviceBody, ctx: Context = Depends(get_context)
) -> IssueDeviceTokenResult:
    result: IssueDeviceTokenResult = bus.send(
        IssueDeviceToken(tournament_id=tournament_id, **body.model_dump()), ctx
    )
    return result
