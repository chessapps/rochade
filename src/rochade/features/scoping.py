"""Resolve which tournament a message acts on.

Authorization is per tournament, but most messages are addressed by game,
round or device. These are the joins that get from one to the other -- pure
mechanics, shared because several messages need exactly the same query.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.shared.models import Device, Game, Round, Section, SectionPlayer


def tournament_of_game(session: Session, game_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        select(Section.tournament_id)
        .join(Round, Round.section_id == Section.id)
        .join(Game, Game.round_id == Round.id)
        .where(Game.id == game_id)
    )


def tournament_of_round(session: Session, round_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        select(Section.tournament_id)
        .join(Round, Round.section_id == Section.id)
        .where(Round.id == round_id)
    )


def tournament_of_section(session: Session, section_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(select(Section.tournament_id).where(Section.id == section_id))


def tournament_of_device(session: Session, device_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(select(Device.tournament_id).where(Device.id == device_id))


def tournament_of_player(session: Session, player_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        select(Section.tournament_id)
        .join(SectionPlayer, SectionPlayer.section_id == Section.id)
        .where(SectionPlayer.id == player_id)
    )
