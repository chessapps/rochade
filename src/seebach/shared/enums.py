"""Enumerations shared by the whole application.

Kept beside the models on purpose: the entities are heavily cross-referenced,
so a per-slice copy of these would only create import gymnastics.
"""

from enum import StrEnum
from typing import Final


class RoundState(StrEnum):
    """Where a round sits in the Vega round-trip.

    OPEN     pairings imported, players may claim results
    CONFIRMED the arbiter has released it; results are final
    EXPORTED  written back to Vega and frozen -- read-only from here on
    """

    OPEN = "open"
    CONFIRMED = "confirmed"
    EXPORTED = "exported"


class ResultState(StrEnum):
    """Trust level of one game's result."""

    EMPTY = "empty"
    CLAIMED = "claimed"
    DISPUTED = "disputed"
    CONFIRMED = "confirmed"


class GameResult(StrEnum):
    """The three outcomes a player may enter at the board.

    Deliberately not the same set as the TRF codes: forfeits and byes are
    arbiter business, and a phone in the hall must not be able to record one.
    """

    WHITE_WIN = "white_win"
    DRAW = "draw"
    BLACK_WIN = "black_win"


class ResultKind(StrEnum):
    """How a result came about -- decides who is allowed to set it."""

    PLAYED = "played"
    FORFEIT = "forfeit"
    BYE = "bye"


class Colour(StrEnum):
    WHITE = "white"
    BLACK = "black"


class Role(StrEnum):
    """Per-tournament staff role, resolved from `tournament_member`."""

    OWNER = "owner"
    ARBITER = "arbiter"
    ASSISTANT = "assistant"


class PrincipalKind(StrEnum):
    STAFF = "staff"
    DEVICE = "device"
    SYSTEM = "system"
    #: Nobody yet: a phone redeeming a join code, before it has a device of its
    #: own. Only `Access.PUBLIC` messages accept it.
    ANONYMOUS = "anonymous"


class EventAction(StrEnum):
    """Every entry in the append-only audit log."""

    ROUND_IMPORTED = "round_imported"
    RESULT_CLAIMED = "result_claimed"
    RESULT_DISPUTED = "result_disputed"
    RESULT_SET = "result_set"
    DISPUTE_RESOLVED = "dispute_resolved"
    ROUND_RELEASED = "round_released"
    ROUND_EXPORTED = "round_exported"
    CLAIM_DROPPED = "claim_dropped"
    DEVICE_ISSUED = "device_issued"
    DEVICE_REVOKED = "device_revoked"


#: (white, black) TRF codes for each player-enterable outcome. The pair form is
#: what the file actually holds, and it is the only shape that can also express
#: a double forfeit, which no single white-side code can.
TRF_CODES: Final[dict[GameResult, tuple[str, str]]] = {
    GameResult.WHITE_WIN: ("1", "0"),
    GameResult.DRAW: ("=", "="),
    GameResult.BLACK_WIN: ("0", "1"),
}

#: Reverse lookup, for reading results back out of an imported file.
RESULT_FROM_CODES: Final[dict[tuple[str, str], GameResult]] = {
    codes: result for result, codes in TRF_CODES.items()
}

#: Codes an arbiter may write that a player may not.
ARBITER_ONLY_CODES: Final[frozenset[str]] = frozenset({"+", "-", "H", "F", "U", "Z", "W", "D", "L"})

#: Every code that may land in a `game` row, for the DB check constraint.
LEGAL_RESULT_CODES: Final[tuple[str, ...]] = (
    "1",
    "=",
    "0",
    "+",
    "-",
    "W",
    "D",
    "L",
    "H",
    "F",
    "U",
    "Z",
    " ",
)
