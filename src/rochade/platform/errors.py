"""Domain errors and their HTTP shape.

Handlers raise these; one exception handler at the edge turns them into
responses. No handler builds an HTTPException itself, so the same command
behaves identically when called from a test through the mediator.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Forbidden(DomainError):
    status_code = 403
    code = "forbidden"


class Unauthenticated(DomainError):
    status_code = 401
    code = "unauthenticated"


class Conflict(DomainError):
    """The request is well-formed but the current state does not allow it."""

    status_code = 409
    code = "conflict"


class ValidationFailed(DomainError):
    status_code = 422
    code = "validation_failed"


class Unavailable(DomainError):
    """Something on our side did not answer: the pairing engine, for instance."""

    status_code = 503
    code = "unavailable"


class RoundFrozen(Conflict):
    """The round is closed: exported to the manager, or the next round was paired on it."""

    code = "round_frozen"


class IdempotencyConflict(Conflict):
    """The same idempotency key arrived with a different request body."""

    code = "idempotency_conflict"
