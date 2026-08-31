"""Cross-field validation.

Pydantic already ran on construction, so this is only for rules that need the
whole message together -- and, deliberately, never for rules that need the
database. Those are preconditions, and preconditions belong to the command.
"""

from __future__ import annotations

from typing import Any

from seebach.platform.mediator import Context, Message, Next


def validate(message: Message, ctx: Context, nxt: Next) -> Any:
    message.check()
    return nxt()
