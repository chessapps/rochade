"""One transaction per command. Queries never open one.

Commands commit here rather than in the handler, so a handler cannot half-apply
a change by returning early.
"""

from __future__ import annotations

from typing import Any

from seebach.platform.mediator import Command, Context, Message, Next


def transaction(message: Message, ctx: Context, nxt: Next) -> Any:
    if not isinstance(message, Command):
        return nxt()
    try:
        result = nxt()
    except Exception:
        ctx.session.rollback()
        raise
    ctx.session.commit()
    return result
