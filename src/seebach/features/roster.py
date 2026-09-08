"""The section's players, in the shape the interchange layer reads them in.

One place for the conversion, because two use cases need the same thing: the
import, so a manager whose export can arrive without its player list still
names every board, and the export, which re-reads a stored source that may be
exactly such a list-less file.
"""

from __future__ import annotations

from seebach.interchange import PlayerRow
from seebach.shared.models import Section


def roster_of(section: Section | None) -> dict[int, PlayerRow]:
    if section is None:
        return {}
    return {
        p.start_rank: PlayerRow(
            start_rank=p.start_rank,
            name=p.name,
            title=p.title,
            rating=p.rating,
            federation=p.federation,
            fide_id=p.fide_id,
            points=p.points,
            tiebreaks=tuple(p.tiebreaks or ()),
            rank=p.rank,
        )
        for p in section.players
    }
