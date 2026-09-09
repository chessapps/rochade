"""Structured log line per message, whatever the outcome."""

from __future__ import annotations

import logging
import time
from typing import Any

from rochade.platform.errors import DomainError
from rochade.platform.mediator import Context, Message, Next

logger = logging.getLogger("rochade.mediator")


def log(message: Message, ctx: Context, nxt: Next) -> Any:
    started = time.perf_counter()
    name = type(message).__name__
    try:
        result = nxt()
    except DomainError as exc:
        logger.info(
            "%s rejected: %s",
            name,
            exc.code,
            extra=_fields(ctx, name, started, outcome=exc.code),
        )
        raise
    except Exception:
        logger.exception("%s failed", name, extra=_fields(ctx, name, started, outcome="error"))
        raise
    logger.info("%s ok", name, extra=_fields(ctx, name, started, outcome="ok"))
    return result


# `message`, `args`, `exc_info`, `name` and friends are reserved on LogRecord:
# passing one through `extra` raises rather than being ignored, so every key
# here is deliberately prefixed.
def _fields(ctx: Context, name: str, started: float, *, outcome: str) -> dict[str, Any]:
    return {
        "rochade_message": name,
        "rochade_outcome": outcome,
        "rochade_duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "rochade_request_id": ctx.request_id,
        "rochade_principal": ctx.principal.subject,
        "rochade_principal_kind": ctx.principal.kind.value,
    }
