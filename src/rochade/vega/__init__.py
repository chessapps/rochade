"""Vega's tournament-folder files, read as pure text.

Vega (www.vegachess.com) never exports the round it has just paired: its FIDE
rating report refuses to save while a game is unfinished, and the round has
no results yet by definition. What it does do, at every pairing and every
manual change to one, is rewrite two plain files in the tournament folder:

- ``crosstable.txt`` -- every player with start number, rating, title and
  federation, and one cell per round played so far;
- ``SortedPairs.txt`` -- the boards of the round just paired, by name.

Together they say what the TRF export would have said. The modules here parse
each one; ``interchange.formats.vega_text`` joins them into a round.

Observed on Vega 12.1.8 -- see ``docs/m0-vega.md``.
"""

from rochade.vega.crosstable import (
    CrossTable,
    CrossTableError,
    CrossTableRow,
    RoundCell,
    looks_like_cross_table,
    parse_cross_table,
)
from rochade.vega.sorted_pairs import (
    SortedPair,
    SortedPairs,
    SortedPairsError,
    looks_like_sorted_pairs,
    parse_sorted_pairs,
)
from rochade.vega.trf_dialect import to_vega

__all__ = [
    "CrossTable",
    "CrossTableError",
    "CrossTableRow",
    "RoundCell",
    "SortedPair",
    "SortedPairs",
    "SortedPairsError",
    "looks_like_cross_table",
    "looks_like_sorted_pairs",
    "parse_cross_table",
    "parse_sorted_pairs",
    "to_vega",
]
