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
