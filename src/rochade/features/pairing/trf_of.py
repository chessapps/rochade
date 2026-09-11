"""A section as the engine reads it: its players and rounds as a TRF16 document.

The mapping from what we store to what the builder wants, and nothing else.
Rounds after `upto_round` are left out, so the tie-breaks after round 3 are
computed from rounds 1 to 3 whatever has been paired since.
"""

from __future__ import annotations

from collections.abc import Mapping

from rochade.shared.models import Section, SectionPlayer
from rochade.trf.build import BuildDocument, BuildPlayer, build
from rochade.trf.model import Colour, RoundEntry


def build_document(
    section: Section,
    *,
    upto_round: int,
    ranks: Mapping[SectionPlayer, int] | None = None,
) -> BuildDocument:
    """`ranks` overrides the stored start ranks -- for a preview of the seeding
    before it is written, when no round exists to refer to them yet."""
    rank_of = {p: (ranks[p] if ranks else p.start_rank) for p in section.players}
    entries: dict[int, dict[int, RoundEntry]] = {rank: {} for rank in rank_of.values()}

    for round_ in section.rounds:
        if round_.number > upto_round:
            continue
        for game in round_.games:
            if game.black_rank is None:
                entries[game.white_rank][round_.number] = RoundEntry(
                    round_no=round_.number,
                    opponent=None,
                    colour=Colour.NONE,
                    result=game.white_result,
                )
                continue
            entries[game.white_rank][round_.number] = RoundEntry(
                round_no=round_.number,
                opponent=game.black_rank,
                colour=Colour.WHITE,
                result=game.white_result,
            )
            entries[game.black_rank][round_.number] = RoundEntry(
                round_no=round_.number,
                opponent=game.white_rank,
                colour=Colour.BLACK,
                result=game.black_result,
            )

    tournament = section.tournament
    return BuildDocument(
        name=f"{tournament.name} - {section.name}",
        city=tournament.city,
        federation=tournament.federation,
        start_date=tournament.start_date.strftime("%Y/%m/%d") if tournament.start_date else "",
        end_date=tournament.end_date.strftime("%Y/%m/%d") if tournament.end_date else "",
        declared_rounds=section.declared_rounds,
        top_colour=section.top_board_colour,
        players=[
            BuildPlayer(
                start_rank=rank_of[player],
                name=player.name,
                sex=player.sex,
                title=player.title,
                rating=player.rating,
                federation=player.federation,
                fide_id=player.fide_id,
                birth_date=player.birth_date,
                rounds=entries[rank_of[player]],
            )
            for player in section.players
        ],
    )


def trf_for_engine(
    section: Section, *, upto_round: int, ranks: Mapping[SectionPlayer, int] | None = None
) -> str:
    return build(build_document(section, upto_round=upto_round, ranks=ranks))
