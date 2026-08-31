"""Deduplicate commands that carry a client-generated key.

The hall app queues claims while offline and retries them when the network
comes back, so the same claim can legitimately arrive several times. Handling
that in one place is the main reason the mediator exists at all.

The record is written inside the command's own transaction, so a command and
its dedupe marker land together or not at all.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from seebach.platform.errors import IdempotencyConflict
from seebach.platform.mediator import Command, Context, Message, Next
from seebach.shared.models import IdempotencyRecord


def idempotency(message: Message, ctx: Context, nxt: Next) -> Any:
    key = ctx.idempotency_key
    if key is None or not isinstance(message, Command):
        return nxt()

    name = type(message).__name__
    fingerprint = _fingerprint(message)

    existing = ctx.session.get(IdempotencyRecord, key)
    if existing is not None:
        return _replay(existing, message, name, fingerprint)

    result = nxt()

    record = IdempotencyRecord(
        key=key,
        command=name,
        request_fingerprint=fingerprint,
        response=_jsonable(result),
    )
    try:
        with ctx.session.begin_nested():
            ctx.session.add(record)
    except IntegrityError:
        # Two retries of the same claim raced. The loser replays the winner
        # rather than reporting a failure the client cannot act on.
        ctx.session.expire_all()
        stored = ctx.session.get(IdempotencyRecord, key)
        if stored is None:
            raise
        return _replay(stored, message, name, fingerprint)
    return result


def _replay(record: IdempotencyRecord, message: Message, name: str, fingerprint: str) -> Any:
    if record.command != name or record.request_fingerprint != fingerprint:
        raise IdempotencyConflict(
            "this idempotency key was already used for a different request",
            key=record.key,
            original_command=record.command,
        )
    model = getattr(type(message), "result_model", None)
    if model is not None:
        return model.model_validate(record.response)
    return record.response


def _fingerprint(message: Message) -> str:
    body = message.model_dump_json()
    return hashlib.sha256(f"{type(message).__name__}:{body}".encode()).hexdigest()


def _jsonable(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    return result
