"""The HTTP edge: build a Context, dispatch, translate errors.

Routes are one line of glue each. Nothing decides anything here -- that is the
point of putting the whole pipeline behind the mediator.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from seebach.platform.auth.principal import current_principal
from seebach.platform.db import get_session
from seebach.platform.mediator import Context, Principal
from seebach.shared.enums import PrincipalKind

ANONYMOUS = Principal(kind=PrincipalKind.ANONYMOUS, subject="")


def get_context(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Context:
    return Context(
        session=session,
        principal=principal,
        request_id=request.headers.get("X-Request-Id") or str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )


def get_public_context(
    request: Request,
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Context:
    """A context for the one thing that happens before there are credentials.

    Only `Access.PUBLIC` messages may be sent with it: everything else asks the
    principal what it is, and an anonymous one is neither staff nor a device.
    """
    return Context(
        session=session,
        principal=ANONYMOUS,
        request_id=request.headers.get("X-Request-Id") or str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
