"""TRF result codes.

The single-character code in column 99 of a round block. Getting these wrong is
the most likely way a round-trip corrupts a tournament, so they live in one
table with their properties attached.
"""

from __future__ import annotations

from typing import Final, NamedTuple

ResultCode = str


class _Spec(NamedTuple):
    points: float
    played: bool
    rated: bool
    description: str


# Ordered as the FIDE spec lists them.
RESULT_CODES: Final[dict[ResultCode, _Spec]] = {
    # Played games, rated.
    "1": _Spec(1.0, True, True, "win"),
    "=": _Spec(0.5, True, True, "draw"),
    "0": _Spec(0.0, True, True, "loss"),
    # Played games, not rated.
    "W": _Spec(1.0, True, False, "win (unrated)"),
    "D": _Spec(0.5, True, False, "draw (unrated)"),
    "L": _Spec(0.0, True, False, "loss (unrated)"),
    # Unplayed games.
    "+": _Spec(1.0, False, False, "forfeit win"),
    "-": _Spec(0.0, False, False, "forfeit loss"),
    "H": _Spec(0.5, False, False, "half-point bye"),
    "F": _Spec(1.0, False, False, "full-point bye"),
    "U": _Spec(1.0, False, False, "pairing-allocated bye"),
    "Z": _Spec(0.0, False, False, "zero-point bye"),
    # No result recorded yet.
    " ": _Spec(0.0, False, False, "no result"),
}

#: Codes a player may submit for a game that was actually played at the board.
PLAYED_CODES: Final[frozenset[str]] = frozenset({"1", "=", "0"})

#: Codes that describe a game nobody sat down for; only an arbiter may set these.
UNPLAYED_CODES: Final[frozenset[str]] = frozenset({"+", "-", "H", "F", "U", "Z"})

#: A result and its mirror on the opponent's row.
_MIRROR: Final[dict[ResultCode, ResultCode]] = {
    "1": "0",
    "0": "1",
    "=": "=",
    "W": "L",
    "L": "W",
    "D": "D",
    "+": "-",
    "-": "+",
    " ": " ",
}


def is_known(code: str) -> bool:
    return code in RESULT_CODES


def is_played(code: str) -> bool:
    spec = RESULT_CODES.get(code)
    return spec is not None and spec.played


def points_for(code: str) -> float:
    spec = RESULT_CODES.get(code)
    if spec is None:
        raise ValueError(f"unknown TRF result code {code!r}")
    return spec.points


def mirror(code: str) -> ResultCode:
    """The code the opponent's row carries for the same game.

    Byes have no opponent row, so they have no mirror and raise.
    """
    try:
        return _MIRROR[code]
    except KeyError:
        raise ValueError(f"result code {code!r} has no opponent side") from None
