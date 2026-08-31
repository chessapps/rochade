"""Structured log line per message, whatever the outcome."""

from __future__ import annotations

import logging
import time
from typing import Any

from seebach.platform.errors import DomainError
from seebach.platform.mediator import Context, Message, Next

logger = logging.getLogger("seebach.mediator")


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


def _fields(ctx: Context, name: str, started: float, *, outcome: str) -> dict[str, Any]:
    return {
        "message": name,
        "outcome": outcome,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "request_id": ctx.request_id,
        "principal": ctx.principal.subject,
        "principal_kind": ctx.principal.kind.value,
    }
