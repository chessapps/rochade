"""Swiss-Manager: TRF16 out of it, its own pairing file back into it.

Verified against Swiss-Manager 15.0.0.3 -- see `docs/m0-swiss-manager.md` for
what was watched. In short:

* `Extras -> Daten Import/Export` writes the paired-but-unplayed round as two
  plain text files: `Spielerdaten` for the players, `Spielerauslosung` for the
  boards. They join on the start number and are read together.
  `Extras -> FIDE-Daten-Export TRF16` was the original inbound leg and is no
  longer asked for: on 15.0.0.3 it dies with an access violation for a
  tournament whose rounds Swiss-Manager paired itself (seen 2026-09-07). TRF16
  is still *read*, because rounds imported before this change are re-read from
  the source they were imported from.
* `Datei -> FIDE-Datenformat importieren TRF16` is **not** the way back: it
  creates a new tournament from the file every time and re-derives settings
  from it. `Extras -> Daten Import/Export -> Spielerauslosung` is: it merges
  results into the tournament that is already open, forfeits included, and the
  next round pairs.

So this adapter reads one format and writes another, which is exactly the case
`Capabilities.reads_format` / `writes_format` were split for.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from rochade.interchange.document import ManagerFile, PlayerRow, ResultEntry, RoundDocument
from rochade.interchange.formats import swiss_manager_text
from rochade.interchange.formats import trf as trf_format
from rochade.interchange.port import Capabilities, InterchangeError, Support, register
from rochade.swiss_manager import PairingFileError, PairingLine, render_pairing_file
from rochade.swiss_manager.pairing_file import WRITABLE_CODES


class SwissManager:
    key: ClassVar[str] = "swiss_manager"
    label: ClassVar[str] = "Swiss-Manager"
    capabilities: ClassVar[Capabilities] = Capabilities(
        exports_unplayed_round=Support.YES,
        merges_on_import=Support.YES,
        # Played results and forfeits, both sides. Byes are Swiss-Manager's own
        # business and go back exactly as they came; unrated results (W/D/L)
        # have no spelling in the pairing file and are refused, not guessed.
        result_codes_out=WRITABLE_CODES,
        reads_format="swiss-manager text exports (trf16 also read)",
        writes_format="swiss-manager pairing file",
        export_howto=(
            "Extras → Daten Import/Export, on the export side: «Spielerdaten (Text-File)» "
            "→ Starten → save, then «Spielerauslosung (Text-File)» → Starten with the "
            "round range → save. Bring both files here. The players file only changes "
            "when the entry list does."
        ),
        import_howto=(
            "Extras → Daten Import/Export → Spielerauslosung → Starten, pick the downloaded "
            "file. The results land in the open tournament; pair the next round as usual."
        ),
        notes=(
            "The results file also carries the pairings, and Swiss-Manager takes them: if a "
            "round was re-paired there after it was exported here, export it again and "
            "re-import it here before sending results back, or the re-pairing is undone.",
            "Its TRF16 export crashes on 15.0.0.3 for a tournament whose rounds it paired "
            "itself, which is why the round comes over as these two text files instead.",
            "Names arrive as Swiss-Manager exports them: «Surname,Given», transliterated for "
            "the tournament's own federation (Müller → Mueller).",
            "Verified against Swiss-Manager 15.0.0.3.",
        ),
    )

    def read_round(
        self, content: str, known_players: Mapping[int, PlayerRow] | None = None
    ) -> RoundDocument:
        """Its own text exports, or a TRF16 -- whichever the file turns out to be.

        The text pair is the way in now (see the module docstring); from round
        two the pairings alone will do, named from the roster we hold. TRF16
        still reads, because rounds imported before this exist and are re-read
        from their stored source every time one is exported again.
        """
        if swiss_manager_text.looks_like(content):
            return swiss_manager_text.read_document(content, known_players)
        return trf_format.read_document(content)

    def write_results(
        self,
        document: RoundDocument,
        round_number: int,
        results: Sequence[ResultEntry],
        *,
        stem: str,
    ) -> ManagerFile:
        by_white = {entry.white_rank: entry for entry in results}
        unplaced = set(by_white)
        lines: list[PairingLine] = []
        for row in document.board_rows(round_number):
            if row.is_bye:
                # Only the pairing-allocated bye is a row in Swiss-Manager's own
                # file; a half-point or zero-point bye is a player status there
                # and writing a row for it would turn it into a pairing.
                if row.white_result != "U":
                    continue
                lines.append(
                    PairingLine(
                        round_no=round_number,
                        board=row.board,
                        white=row.white_rank,
                        black=None,
                        white_id=_ident(document, row.white_rank),
                    )
                )
                continue
            entry = by_white.get(row.white_rank)
            unplaced.discard(row.white_rank)
            white, black = (entry.white_result, entry.black_result) if entry else (" ", " ")
            lines.append(
                PairingLine(
                    round_no=round_number,
                    board=row.board,
                    white=row.white_rank,
                    black=row.black_rank,
                    white_result=white,
                    black_result=black,
                    white_id=_ident(document, row.white_rank),
                    black_id=_ident(document, row.black_rank),
                )
            )
        if unplaced:
            raise InterchangeError(
                f"results for white players {sorted(unplaced)} have no board in round "
                f"{round_number} of the file this round was imported from"
            )
        try:
            content = render_pairing_file(lines)
        except PairingFileError as exc:
            raise InterchangeError(str(exc)) from exc
        return ManagerFile(filename=f"{stem}.txt", content=content)


def _ident(document: RoundDocument, rank: int | None) -> str:
    """The FIDE id Swiss-Manager would write, or its `0` for none.

    Observed only with players who have none. Swiss-Manager matched rows by
    start number, so this is passthrough of what its own export would hold.
    """
    if rank is None:
        return "0"
    player = document.players.get(rank)
    fide_id = (player.fide_id or "").strip() if player else ""
    return fide_id if fide_id and fide_id != "0" else "0"


register(SwissManager())
