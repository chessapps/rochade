"""Append to the audit log.

Shared mechanics, not policy: every caller decides for itself what happened and
what is worth recording. This only knows how to write the row -- and how to
anchor it to the natural key, so that a re-import which rebuilds the section
cannot orphan the history of who entered what.
"""

from __future__ import annotations

from typing import Any

from seebach.platform.mediator import Context
from seebach.shared.enums import EventAction
from seebach.shared.models import Game, GameEvent


def record(
    ctx: Context,
    *,
    section_id: Any,
    round_number: int,
    action: EventAction,
    game: Game | None = None,
    **payload: Any,
) -> GameEvent:
    event = GameEvent(
        section_id=section_id,
        round_number=round_number,
        white_name=game.white_name if game else None,
        black_name=game.black_name if game else None,
        action=action,
        payload=payload,
        actor_kind=ctx.principal.kind,
        actor_subject=ctx.principal.subject,
        device_id=ctx.principal.device_id,
        ip=ctx.ip,
        user_agent=(ctx.user_agent or "")[:255] or None,
    )
    ctx.session.add(event)
    return event
