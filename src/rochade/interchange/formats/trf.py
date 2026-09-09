"""TRF16 as adapters see it: one file in, a `RoundDocument` out, and back.

Both Vega and Swiss-Manager hand us TRF16, so the reading half is shared. The
writing half is only Vega's -- Swiss-Manager takes its results back in its own
pairing file -- but it lives here because it is a property of the format, not of
the program: patch the result cells, move points by delta, re-emit everything
else byte for byte.
"""

from __future__ import annotations

from collections.abc import Sequence

from rochade.interchange.document import PairingRow, PlayerRow, ResultEntry, RoundDocument
from rochade.interchange.port import InterchangeError
from rochade.trf import Dialect, TrfParseError, parse, serialize
from rochade.trf.edit import set_result


def read_document(content: str) -> RoundDocument:
    try:
        trf = parse(content)
    except TrfParseError as exc:
        raise InterchangeError(str(exc), line_no=exc.line_no) from exc

    def name_of(rank: int, round_no: int) -> str:
        player = trf.players.get(rank)
        if player is None:
            # Some row points at an opponent that has no 001 line. The file is
            # damaged; the import preview is where that should be said.
            raise InterchangeError(
                f"round {round_no} pairs a player with starting rank {rank}, "
                "but the file has no such player"
            )
        return player.name

    pairings = {
        round_no: [
            PairingRow(
                board=pairing.board,
                white_rank=pairing.white,
                white_name=name_of(pairing.white, round_no),
                black_rank=pairing.black,
                black_name=(
                    name_of(pairing.black, round_no) if pairing.black is not None else None
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
    document: RoundDocument, round_number: int, results: Sequence[ResultEntry], dialect: Dialect
) -> str:
    try:
        trf = parse(document.source)
    except TrfParseError as exc:  # pragma: no cover - it parsed on import
        raise InterchangeError(str(exc), line_no=exc.line_no) from exc
    for entry in results:
        set_result(
            trf,
            round_number,
            entry.white_rank,
            entry.white_result,
            opponent_code=entry.black_result if entry.black_result != " " else None,
        )
    return serialize(trf, dialect)
