"""Dispatch, and the seam the pipeline behaviours hang off.

Deliberately small. It earns its place on two behaviours specifically:
idempotency, because kiosk claims arrive from an offline retry queue and must
dedupe in exactly one place, and authorization, because every message is
tournament- and role-scoped. It should not grow beyond that.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from rochade.platform.errors import Forbidden
from rochade.shared.enums import PrincipalKind, Role


class Access(StrEnum):
    """Who may send a message.

    Staff levels are ordered: an owner satisfies an arbiter requirement.
    """

    OWNER = "owner"
    ARBITER = "arbiter"
    STAFF = "staff"
    DEVICE = "device"
    PUBLIC = "public"


ROLE_RANK = {Role.ASSISTANT: 1, Role.ARBITER: 2, Role.OWNER: 3}
ACCESS_RANK = {Access.STAFF: 1, Access.ARBITER: 2, Access.OWNER: 3}


@dataclass(frozen=True)
class Principal:
    kind: PrincipalKind
    subject: str
    device_id: uuid.UUID | None = None
    #: Set for device tokens, which are minted for exactly one tournament.
    tournament_id: uuid.UUID | None = None

    @property
    def is_staff(self) -> bool:
        return self.kind is PrincipalKind.STAFF

    def require_staff(self) -> None:
        if not self.is_staff:
            raise Forbidden("this action requires a signed-in staff account")


SYSTEM = Principal(kind=PrincipalKind.SYSTEM, subject="system")


@dataclass
class Context:
    """Everything a handler may need that is not part of the message itself."""

    session: Session
    principal: Principal = SYSTEM
    request_id: str = ""
    idempotency_key: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    #: Filled in by the authorize behaviour so handlers need not re-resolve it.
    role: Role | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class Message(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    access: ClassVar[Access] = Access.OWNER

    def tournament_scope(self, session: Session) -> uuid.UUID | None:
        """Which tournament this message acts on, for authorization.

        The default covers messages that carry the id directly. Messages
        addressed by round or section override it.
        """
        return getattr(self, "tournament_id", None)

    def check(self) -> None:
        """Cross-field validation beyond what pydantic does on construction."""


class Command(Message):
    """Mutates state. Runs inside one transaction."""

    #: Set when the command returns a model, so an idempotent replay can hand
    #: back the same type the first call did rather than a bare dict.
    result_model: ClassVar[type[BaseModel] | None] = None


class Query(Message):
    """Reads state. Never writes."""

    access: ClassVar[Access] = Access.STAFF


TMessage = TypeVar("TMessage", bound=Message)

Next = Callable[[], Any]
Behaviour = Callable[[Message, Context, Next], Any]
Handler = Callable[[Any, Context], Any]


class Mediator:
    def __init__(self, behaviours: Sequence[Behaviour] = ()) -> None:
        self._handlers: dict[type[Message], Handler] = {}
        self._behaviours = list(behaviours)

    def register(self, message_type: type[TMessage]) -> Callable[[Handler], Handler]:
        def decorate(handler: Handler) -> Handler:
            if message_type in self._handlers:
                raise RuntimeError(f"{message_type.__name__} already has a handler")
            self._handlers[message_type] = handler
            return handler

        return decorate

    def handler_for(self, message_type: type[Message]) -> Handler:
        try:
            return self._handlers[message_type]
        except KeyError:
            raise RuntimeError(f"no handler registered for {message_type.__name__}") from None

    def send(self, message: Message, ctx: Context) -> Any:
        handler = self.handler_for(type(message))

        def call() -> Any:
            return handler(message, ctx)

        chain: Next = call
        for behaviour in reversed(self._behaviours):
            chain = _bind(behaviour, message, ctx, chain)
        return chain()

    @property
    def registered(self) -> list[type[Message]]:
        return list(self._handlers)


def _bind(behaviour: Behaviour, message: Message, ctx: Context, nxt: Next) -> Next:
    def run() -> Any:
        return behaviour(message, ctx, nxt)

    return run
