"""Vega, over TRF16 in both directions.

Vega computes its Swiss pairings by delegating to JaVaFo, so there is nothing
to gain from talking to it at the pairing-engine level -- the seam belongs at
the manager, which is what this adapter is.

Results are written by patching the file Vega gave us rather than rebuilding
it, so every field Vega wrote that we never modelled goes back unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from rochade.interchange.document import ManagerFile, PlayerRow, ResultEntry, RoundDocument
from rochade.interchange.formats import trf as trf_format
from rochade.interchange.port import Capabilities, Support, register
from rochade.trf import Dialect
from rochade.trf.results import RESULT_CODES


class VegaManager:
    key: ClassVar[str] = "vega"
    label: ClassVar[str] = "Vega"
    capabilities: ClassVar[Capabilities] = Capabilities(
        # Both UNVERIFIED until M0 is run against a real install. Everything we
        # believe about Vega here comes from documentation, and documentation is
        # exactly what M0 exists to distrust -- Swiss-Manager's TRF import turned
        # out to create a new tournament rather than merge, and nothing in its
        # manual said so.
        exports_unplayed_round=Support.UNVERIFIED,
        merges_on_import=Support.UNVERIFIED,
        # TRF is the only format in the loop that can carry the whole result
        # vocabulary, forfeits and byes included, so nothing is dropped.
        result_codes_out=frozenset(code for code in RESULT_CODES if code.strip()),
        reads_format="trf16",
        writes_format="trf16",
        export_howto="Export the tournament as TRF16 with the paired round included.",
        import_howto="Import the downloaded TRF16 over the tournament, then pair the next round.",
        notes=(
            "Vega's TRF import was reworked in 10.5.0; merge behaviour is unconfirmed.",
            "Points move by the delta of results we wrote, never a full recompute.",
        ),
    )

    #: The dialect we emit. Named explicitly -- never serialize "TRF" generically.
    dialect: ClassVar[Dialect] = Dialect.TRF16

    def read_round(
        self, content: str, known_players: Mapping[int, PlayerRow] | None = None
    ) -> RoundDocument:
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
        return ManagerFile(
            filename=f"{stem}.trf",
            content=trf_format.write_results(document, round_number, results, self.dialect),
        )


register(VegaManager())
