"""A short code a phone can type instead of scanning the QR.

The QR is the right thing in a hall: it is one gesture and it carries a token
nobody could type. It is the wrong thing everywhere else -- a phone on another
network, a tester without a camera, an arbiter reading something out to a
player whose camera app will not focus. So a tournament may also hold a **join
code**: six unambiguous characters that mint a device of their own when
redeemed.

Redeeming is unauthenticated, which is exactly as much access as the QR link
already grants -- anyone holding either can enter results as a phone in that
hall. The difference is that a code is short enough to guess at, so it is off
unless `ROCHADE_DEVICE_JOIN_ENABLED` says otherwise, it is one click to rotate
or turn off, and every device it mints is revocable and named in the audit log.
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from rochade.platform.bus import bus
from rochade.platform.errors import NotFound
from rochade.platform.http import get_context
from rochade.platform.mediator import Access, Command, Context
from rochade.shared.models import Tournament

router = APIRouter(prefix="/tournaments", tags=["devices"])

#: No I, O, 0 or 1: this gets read out loud across a playing hall.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LENGTH = 6


class JoinCodeResult(BaseModel):
    #: None once joining is turned off.
    join_code: str | None


class SetJoinCode(Command):
    access = Access.ARBITER
    result_model = JoinCodeResult

    tournament_id: uuid.UUID
    #: False clears the code, which stops any further joining at once. Devices
    #: already minted keep working until they expire or are revoked.
    enabled: bool = True


@bus.register(SetJoinCode)
def handle(command: SetJoinCode, ctx: Context) -> JoinCodeResult:
    tournament = ctx.session.get(Tournament, command.tournament_id)
    if tournament is None:
        raise NotFound("tournament not found", tournament_id=str(command.tournament_id))

    tournament.join_code = _unique_code(ctx) if command.enabled else None
    ctx.session.flush()
    return JoinCodeResult(join_code=tournament.join_code)


def normalise(code: str) -> str:
    """What someone typed, as the database holds it: no spaces, no dashes."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _unique_code(ctx: Context) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        taken = ctx.session.scalar(select(Tournament.id).where(Tournament.join_code == code))
        if taken is None:
            return code
    raise RuntimeError("could not find a free join code")  # pragma: no cover - 32^6 codes


@router.post("/{tournament_id}/join-code", response_model=JoinCodeResult)
def set_join_code(tournament_id: uuid.UUID, ctx: Context = Depends(get_context)) -> JoinCodeResult:
    result: JoinCodeResult = bus.send(SetJoinCode(tournament_id=tournament_id), ctx)
    return result


@router.delete("/{tournament_id}/join-code", response_model=JoinCodeResult)
def clear_join_code(
    tournament_id: uuid.UUID, ctx: Context = Depends(get_context)
) -> JoinCodeResult:
    result: JoinCodeResult = bus.send(SetJoinCode(tournament_id=tournament_id, enabled=False), ctx)
    return result
