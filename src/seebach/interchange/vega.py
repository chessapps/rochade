"""Vega, over TRF16 in both directions.

Vega computes its Swiss pairings by delegating to JaVaFo, so there is nothing
to gain from talking to it at the pairing-engine level -- the seam belongs at
the manager, which is what this adapter is.

Results are written by patching the file Vega gave us rather than rebuilding
it, so every field Vega wrote that we never modelled goes back unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from seebach.interchange.document import (
    ManagerFile,
    PairingRow,
    PlayerRow,
    ResultEntry,
    RoundDocument,
)
from seebach.interchange.port import Capabilities, InterchangeError, Support, register
from seebach.trf import Dialect, TrfParseError, parse, serialize
from seebach.trf.edit import set_result
from seebach.trf.results import RESULT_CODES


class VegaManager:
    key: ClassVar[str] = "vega"
    label: ClassVar[str] = "Vega"
    capabilities: ClassVar[Capabilities] = Capabilities(
        # Both UNVERIFIED until M0 is run against a real install. Everything we
        # believe about Vega here comes from documentation, and documentation is
        # exactly what M0 exists to distrust.
        exports_unplayed_round=Support.UNVERIFIED,
        merges_on_import=Support.UNVERIFIED,
        # TRF is the only format in the loop that can carry the whole result
        # vocabulary, forfeits and byes included, so nothing is dropped.
        result_codes_out=frozenset(code for code in RESULT_CODES if code.strip()),
        reads_format="trf16",
        writes_format="trf16",
        notes=(
            "Vega's TRF import was reworked in 10.5.0; merge behaviour is unconfirmed.",
            "Points move by the delta of results we wrote, never a full recompute.",
        ),
    )

    #: The dialect we emit. Named explicitly -- never serialize "TRF" generically.
    dialect: ClassVar[Dialect] = Dialect.TRF16

    def read_round(self, content: str) -> RoundDocument:
        try:
            trf = parse(content)
        except TrfParseError as exc:
            raise InterchangeError(str(exc), line_no=exc.line_no) from exc
        pairings = {
            round_no: [
                PairingRow(
                    board=pairing.board,
                    white_rank=pairing.white,
                    white_name=trf.players[pairing.white].name,
                    black_rank=pairing.black,
                    black_name=(
                        trf.players[pairing.black].name if pairing.black is not None else None
                    ),
                    white_result=pairing.white_result,
                    black_result=pairing.black_result,
                )
                for pairing in trf.pairings(round_no)
            ]
            for round_no in range(1, trf.rounds_present + 1)
        }

        return RoundDocument(
            round_number=trf.rounds_present,
            players={
                rank: PlayerRow(
                    start_rank=rank,
                    name=player.name,
                    title=player.title,
                    rating=player.rating,
                    federation=player.federation,
                    fide_id=player.fide_id,
                )
                for rank, player in trf.players.items()
            },
            pairings=pairings,
            source=content,
            tournament_name=trf.name,
            declared_rounds=trf.declared_rounds,
            unknown_result_codes=list(trf.unknown_result_codes),
        )

    def write_results(
        self,
        document: RoundDocument,
        round_number: int,
        results: Sequence[ResultEntry],
        *,
        stem: str,
    ) -> ManagerFile:
        try:
            trf = parse(document.source)
        except TrfParseError as exc:  # pragma: no cover - it parsed on import
            raise InterchangeError(str(exc), line_no=exc.line_no) from exc
        for entry in results:
            set_result(trf, round_number, entry.white_rank, entry.white_result)
        return ManagerFile(
            filename=f"{stem}.trf",
            content=serialize(trf, self.dialect),
        )


register(VegaManager())
