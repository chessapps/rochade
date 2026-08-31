"""Turn an incoming request into a Principal.

Two credential kinds, deliberately separate: a staff OIDC bearer token, and a
device token that the app minted itself. A device token can never widen into
staff access, because it is not the same header value and not the same lookup.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.platform.auth.tokens import hash_token
from seebach.platform.config import settings
from seebach.platform.db import get_session
from seebach.platform.errors import Unauthenticated
from seebach.platform.mediator import Principal
from seebach.shared.enums import PrincipalKind
from seebach.shared.models import Device

DEVICE_SCHEME = "device"
BEARER_SCHEME = "bearer"


def current_principal(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Principal:
    if not authorization:
        raise Unauthenticated("no credentials supplied")

    scheme, _, credential = authorization.partition(" ")
    scheme = scheme.lower()
    credential = credential.strip()
    if not credential:
        raise Unauthenticated("malformed Authorization header")

    if scheme == DEVICE_SCHEME:
        return _device_principal(credential, session)
    if scheme == BEARER_SCHEME:
        return _staff_principal(credential)
    raise Unauthenticated(f"unsupported authorization scheme {scheme!r}")


def _device_principal(token: str, session: Session) -> Principal:
    device = session.scalar(select(Device).where(Device.token_hash == hash_token(token)))
    if device is None:
        raise Unauthenticated("unknown device token")
    if device.revoked_at is not None:
        raise Unauthenticated("this device has been revoked")
    if device.expires_at <= datetime.now(UTC):
        raise Unauthenticated("this device token has expired")

    device.last_seen_at = datetime.now(UTC)
    session.commit()

    return Principal(
        kind=PrincipalKind.DEVICE,
        subject=f"device:{device.id}",
        device_id=device.id,
        tournament_id=device.tournament_id,
    )


def _staff_principal(credential: str) -> Principal:
    config = settings()
    if config.oidc_issuer:
        return _oidc_principal(credential)
    if not config.dev_auth_enabled:
        raise Unauthenticated("staff authentication is not configured")
    # Bootstrap mode for M1-M3: the bearer value is the subject. Zitadel lands
    # in M4 and the API only ever sees a standard OIDC JWT, so nothing else
    # changes when it does.
    return Principal(kind=PrincipalKind.STAFF, subject=credential)


def _oidc_principal(credential: str) -> Principal:
    from seebach.platform.auth.oidc import verify

    claims = verify(credential)
    return Principal(kind=PrincipalKind.STAFF, subject=str(claims["sub"]))
