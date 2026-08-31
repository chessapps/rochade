"""TRF(x) — FIDE Data Exchange Format.

A pure library: no database, no FastAPI. Parse a tournament file into a typed
model that retains every byte we do not understand, patch the results we own,
and serialize back. Round-trip identity for untouched input is the contract.
"""

from seebach.trf.dialect import Dialect
from seebach.trf.errors import TrfParseError
from seebach.trf.model import Colour, Pairing, Player, RoundEntry, TrfFile, TrfLine
from seebach.trf.parse import parse
from seebach.trf.results import RESULT_CODES, ResultCode, is_played, points_for
from seebach.trf.serialize import serialize

__all__ = [
    "RESULT_CODES",
    "Colour",
    "Dialect",
    "Pairing",
    "Player",
    "ResultCode",
    "RoundEntry",
    "TrfFile",
    "TrfLine",
    "TrfParseError",
    "is_played",
    "parse",
    "points_for",
    "serialize",
]
