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

from rochade.platform.auth.oidc import looks_like_jwt
from rochade.platform.auth.tokens import hash_token
from rochade.platform.config import settings
from rochade.platform.db import get_session
from rochade.platform.errors import Unauthenticated
from rochade.platform.mediator import Principal
from rochade.shared.enums import PrincipalKind
from rochade.shared.models import Device

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
    if config.oidc_enabled and (looks_like_jwt(credential) or not config.dev_auth_enabled):
        return _oidc_principal(credential)
    if not config.dev_auth_enabled:
        raise Unauthenticated(
            "staff authentication is not configured; set ROCHADE_OIDC_ISSUER, or "
            "ROCHADE_DEV_AUTH_ENABLED=true for local development"
        )
    # Bootstrap mode: the bearer value is the subject. Only reachable when it
    # was asked for, and never for a value shaped like a JWT, so a rejected
    # Zitadel token cannot fall through to "trust it anyway".
    return Principal(kind=PrincipalKind.STAFF, subject=credential)


def _oidc_principal(credential: str) -> Principal:
    from rochade.platform.auth.oidc import verify

    claims = verify(credential)
    return Principal(kind=PrincipalKind.STAFF, subject=str(claims["sub"]))
