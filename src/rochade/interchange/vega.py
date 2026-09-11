"""Vega: its tournament-folder files in, a TRF it imports out.

Verified against Vega 12.1.8 (8 September 2026), English UI, Windows 11, on
2026-09-11 -- see `docs/m0-vega.md` for what was watched.

The documented path in, `Rating Report -> FIDE`, is **not** the way: it
refuses to save while a paired round has no results ("In round 3 table 1
there is an unfinished game. Please insert the result or no report will be
saved"). What Vega does write, at every pairing and every manual change to
one, is `SortedPairs.txt` in the tournament folder -- the boards of the new
round -- and beside it, every time its engine runs, `engine26.trf`: the TRF
it hands the engine, with every player and every result so far, the colours,
the byes and the round count, from round 1 on. Those two files are the
round. `crosstable.txt` is taken in the TRF's place, but Vega writes it only
once a result exists, so it cannot start a tournament. `engine.man` is the
engine's raw output and goes stale the moment the arbiter edits a board, so
it is not read.

The way back is `File -> Import tournament in FIDE format - TRF2026`. Vega
does not merge: it replaces the open tournament with the file, in the same
folder, renamed after the file's stem -- so the file is named after the
section and stays the same name every round. It counts bytes, not
characters, and reads the round count from its own `142` line; `to_vega`
handles both. Points, forfeits and byes come back as written and the next
round pairs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from rochade.interchange.document import ManagerFile, PlayerRow, ResultEntry, RoundDocument
from rochade.interchange.formats import trf as trf_format
from rochade.interchange.formats import vega_text
from rochade.interchange.port import Capabilities, Support, register
from rochade.trf import Dialect
from rochade.vega import to_vega

#: What Vega's import demonstrably kept (`docs/m0-vega.md`, check 6). The
#: unrated `W D L` codes were not tried and are refused rather than guessed.
WRITABLE_CODES = frozenset({"1", "=", "0", "+", "-", "U", "H", "Z"})


class VegaManager:
    key: ClassVar[str] = "vega"
    label: ClassVar[str] = "Vega"
    capabilities: ClassVar[Capabilities] = Capabilities(
        exports_unplayed_round=Support.YES,
        merges_on_import=Support.YES,
        result_codes_out=WRITABLE_CODES,
        reads_format="vega tournament folder: engine26.trf (or crosstable.txt) + SortedPairs.txt",
        writes_format="trf16 for Vega",
        export_howto=(
            "Pair the round, then take engine26.trf and SortedPairs.txt from the "
            "tournament folder (both are rewritten when the engine pairs)."
        ),
        import_howto=(
            "File → Import tournament in FIDE format - TRF2026, choose the file; the "
            "results and the round count arrive with it. Then pair the next round."
        ),
        notes=(
            "The import replaces the open tournament with the file and names it after "
            "the file; tie-breaks other than Buchholz are reset to Vega's default, so "
            "set them again if Vega's own standings matter.",
            "Verified against Vega 12.1.8.",
        ),
    )

    #: The dialect we emit before Vega's own adjustments. Never "TRF" generically.
    dialect: ClassVar[Dialect] = Dialect.TRF16

    def read_round(
        self, content: str, known_players: Mapping[int, PlayerRow] | None = None
    ) -> RoundDocument:
        if vega_text.looks_like(content):
            return vega_text.read_document(content, known_players)
        # A TRF carries its own players; nothing held here is needed.
        return trf_format.read_document(content)

    def write_results(
        self,
        document: RoundDocument,
        round_number: int,
        results: Sequence[ResultEntry],
        *,
        stem: str,
    ) -> ManagerFile:
        content = trf_format.write_results(document, round_number, results, self.dialect)
        return ManagerFile(
            filename=f"{stem}.trf",
            content=to_vega(content, declared_rounds=document.declared_rounds),
        )


register(VegaManager())
