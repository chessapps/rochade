"""The starting order of a section Rochade pairs itself.

Entered players hold provisional numbers in the order they were typed in.
The first pairing seeds them the way C.04.2 says: by rating, then title,
then name -- and from then on the numbers are final, because every board
and every audit line refers to them.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import object_session

from rochade.shared.models import Section, SectionPlayer

#: C.04.2.C: rating first, then the title in this order, then alphabetically.
TITLE_ORDER = ("GM", "IM", "WGM", "FM", "WIM", "CM", "WFM", "WCM")


def seeding_order(players: Sequence[SectionPlayer]) -> list[SectionPlayer]:
    def key(player: SectionPlayer) -> tuple[int, int, str, int]:
        title = player.title.upper()
        return (
            -(player.rating or 0),
            TITLE_ORDER.index(title) if title in TITLE_ORDER else len(TITLE_ORDER),
            player.name.casefold(),
            player.start_rank,
        )

    return sorted(players, key=key)


def provisional_ranks(players: Sequence[SectionPlayer]) -> dict[SectionPlayer, int]:
    return {player: i for i, player in enumerate(seeding_order(players), start=1)}


def seed(section: Section) -> bool:
    """Renumber the section's players into seeding order. True if anything moved.

    Two passes, because `(section_id, start_rank)` is unique and a direct
    swap would collide half way through.
    """
    ranks = provisional_ranks(section.players)
    if all(player.start_rank == rank for player, rank in ranks.items()):
        return False
    session = object_session(section)
    if session is None:  # pragma: no cover - a section is only ever loaded through one
        raise RuntimeError("the section is not attached to a session")
    for player, rank in ranks.items():
        player.start_rank = -rank
    session.flush()
    for player, rank in ranks.items():
        player.start_rank = rank
    session.flush()
    return True
