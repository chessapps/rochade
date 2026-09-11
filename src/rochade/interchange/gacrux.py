"""Rochade as its own tournament manager, with the Gacrux engine underneath.

The third adapter, and the one the port was shaped for: it owns the player
list, pairs each round and computes the standings without a file existing at
all. `read_round` still works, over the TRF the pairing feature stores with
every round it pairs, so a stored round can be read back the way any other
manager's export can. `write_results` has no meaning here and says so.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from rochade.interchange.document import ManagerFile, PlayerRow, ResultEntry, RoundDocument
from rochade.interchange.formats import trf as trf_format
from rochade.interchange.port import Capabilities, InterchangeError, Support, register
from rochade.trf.results import RESULT_CODES


class GacruxManager:
    key: ClassVar[str] = "gacrux"
    label: ClassVar[str] = "Rochade (Gacrux engine)"
    capabilities: ClassVar[Capabilities] = Capabilities(
        native=True,
        # There is no export and no import; the flags describe a file round
        # trip that never happens. YES rather than UNVERIFIED because nothing
        # here is a claim about another program's behaviour.
        exports_unplayed_round=Support.YES,
        merges_on_import=Support.YES,
        result_codes_out=frozenset(code for code in RESULT_CODES if code.strip()),
        reads_format="trf16",
        writes_format="",
        export_howto="",
        import_howto="",
        notes=(
            "Pairs with the FIDE Dutch system and ranks with FIDE tie-breaks, "
            "using the Gacrux engine (TieBreakServer, FIDE / Otto Milvang).",
            "Not FIDE-endorsed.",
        ),
    )

    def read_round(
        self, content: str, known_players: Mapping[int, PlayerRow] | None = None
    ) -> RoundDocument:
        return trf_format.read_document(content)

    def write_results(
        self,
        document: RoundDocument,
        round_number: int,
        results: Sequence[ResultEntry],
        *,
        stem: str,
    ) -> ManagerFile:
        raise InterchangeError("this section is paired in Rochade; there is no file to write")


register(GacruxManager())
