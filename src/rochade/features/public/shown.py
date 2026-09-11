"""The pieces the public queries share: finding a published tournament, and
turning a game's two TRF codes into what a spectator reads.

A result is shown, never scored: points, tie-breaks and ranks are the
manager's numbers as imported, and this module does not add any up.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from fastapi import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.platform.errors import NotFound
from rochade.shared.enums import ResultState, RoundState
from rochade.shared.models import Game, Round, Section, SectionPlayer, Tournament

#: Public answers are the same for everybody and change at most every few
#: seconds, so a cache in front of the API may hold them this long.
CACHE_CONTROL = "public, max-age=15"


def cacheable(response: Response) -> None:
    response.headers["Cache-Control"] = CACHE_CONTROL


class Shown(StrEnum):
    """How far a result can be trusted, as the public sees it.

    Claims are never exposed: a disputed board is preliminary like a claimed
    one, with the result that stands, and nothing says two people disagreed.
    """

    PENDING = "pending"
    PRELIMINARY = "preliminary"
    CONFIRMED = "confirmed"


class Side(BaseModel):
    start_rank: int
    name: str
    title: str = ""
    rating: int | None = None
    federation: str = ""


def published_tournament(session: Session, slug: str) -> Tournament:
    tournament = session.scalar(
        select(Tournament).where(Tournament.slug == slug, Tournament.published.is_(True))
    )
    if tournament is None:
        raise NotFound("tournament not found", slug=slug)
    return tournament


def section_of(tournament: Tournament, section_id: uuid.UUID) -> Section:
    for section in tournament.sections:
        if section.id == section_id:
            return section
    raise NotFound("section not found", section_id=str(section_id))


def sides_of(section: Section) -> dict[int, Side]:
    """Every player of the section by start rank, as a board names them."""
    return {
        player.start_rank: Side(
            start_rank=player.start_rank,
            name=player.name,
            title=player.title,
            rating=player.rating,
            federation=player.federation,
        )
        for player in section.players
    }


def side_from_game(sides: dict[int, Side], rank: int, name: str) -> Side:
    # A board names its players itself, so a re-imported list never leaves a
    # board nameless; the list adds title and rating when it has the player.
    return sides.get(rank) or Side(start_rank=rank, name=name)


def shown_state(game: Game, round_: Round) -> Shown:
    if game.white_result == " ":
        return Shown.PENDING
    if game.state is ResultState.CONFIRMED or round_.state is not RoundState.OPEN:
        return Shown.CONFIRMED
    return Shown.PRELIMINARY


_POINTS: dict[str, float] = {
    "1": 1.0,
    "W": 1.0,
    "+": 1.0,
    "U": 1.0,
    "F": 1.0,
    "=": 0.5,
    "D": 0.5,
    "H": 0.5,
    "0": 0.0,
    "L": 0.0,
    "-": 0.0,
    "Z": 0.0,
}

_HALF = {1.0: "1", 0.5: "½", 0.0: "0"}


def points_of(code: str) -> float | None:
    """What one side's TRF code is worth; None when there is no result yet."""
    return _POINTS.get(code)


def shown_result(game: Game) -> str:
    """``1-0``, ``½-½``, ``0-1``; forfeits ``+:-``; a bye's own score; blank while pending."""
    if game.black_rank is None:
        points = points_of(game.white_result)
        return "" if points is None else _HALF[points]
    white, black = game.white_result, game.black_result
    if white in "+-" and white != " ":
        return f"{white}:{black}"
    left, right = points_of(white), points_of(black)
    if left is None:
        return ""
    if right is None:
        right = 1.0 - left
    return f"{_HALF[left]}-{_HALF[right]}"


def player_of(section: Section, start_rank: int) -> SectionPlayer:
    for player in section.players:
        if player.start_rank == start_rank:
            return player
    raise NotFound("player not found", start_rank=start_rank)
