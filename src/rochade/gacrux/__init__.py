"""The Gacrux engine: FIDE Dutch pairings and C.07 tie-breaks, in process.

A thin wrapper over the vendored TieBreakServer (`vendor/tiebreakserver`,
MIT, FIDE / Otto Milvang). Pure: no database, no framework. The interchange
is FIDE TRF16 text, which `rochade.trf` already reads and writes, so nothing
here knows about any program's file format either.
"""

from rochade.gacrux.engine import (
    EngineError,
    EnginePair,
    EngineStanding,
    engine_dir,
    pair,
    standings,
)
from rochade.gacrux.tiebreaks import DEFAULT_TIEBREAKS, KNOWN_TIEBREAKS, validate_tiebreaks

__all__ = [
    "DEFAULT_TIEBREAKS",
    "KNOWN_TIEBREAKS",
    "EngineError",
    "EnginePair",
    "EngineStanding",
    "engine_dir",
    "pair",
    "standings",
    "validate_tiebreaks",
]
