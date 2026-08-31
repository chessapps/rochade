"""Every SQLAlchemy model in the application.

Anemic on purpose: columns, relationships and constraints, no behaviour. All
state transitions live in the commands that own them. Invariants that must not
be bypassable live here as check constraints, because a command can forget to
call a helper but cannot forget the database.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from seebach.shared.enums import EventAction, PrincipalKind, ResultState, Role, RoundState

Json = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _enum(enum_type: type, name: str) -> Enum:
    return Enum(enum_type, name=name, native_enum=False, validate_strings=True, length=32)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: Json}


class Tournament(Base):
    __tablename__ = "tournament"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(120), default="")
    federation: Mapped[str] = mapped_column(String(8), default="")
    start_date: Mapped[date | None] = mapped_column(Date(), default=None)
    end_date: Mapped[date | None] = mapped_column(Date(), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sections: Mapped[list[Section]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan", order_by="Section.name"
    )
    members: Mapped[list[TournamentMember]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )
    devices: Mapped[list[Device]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )


class TournamentMember(Base):
    """Staff access, scoped per tournament. `subject` is the OIDC `sub` claim."""

    __tablename__ = "tournament_member"
    __table_args__ = (UniqueConstraint("tournament_id", "subject", name="uq_member_subject"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournament.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[Role] = mapped_column(_enum(Role, "role"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tournament: Mapped[Tournament] = relationship(back_populates="members")


class Section(Base):
    """One Vega file. A tournament may hold several (groups A/B/C).

    The hall app searches across all sections at once, which is the thing Vega
    itself cannot do -- it is one tournament per file.
    """

    __tablename__ = "section"
    __table_args__ = (UniqueConstraint("tournament_id", "name", name="uq_section_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournament.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    declared_rounds: Mapped[int | None] = mapped_column(Integer(), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tournament: Mapped[Tournament] = relationship(back_populates="sections")
    players: Mapped[list[SectionPlayer]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="SectionPlayer.start_rank"
    )
    rounds: Mapped[list[Round]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="Round.number"
    )


class SectionPlayer(Base):
    """A player as this section's file describes them.

    Not a person registry. v1 has no identity model: Vega owns identity, and
    each import is a self-contained document, so these rows are rebuilt from
    the file rather than reconciled against anything.
    """

    __tablename__ = "section_player"
    __table_args__ = (UniqueConstraint("section_id", "start_rank", name="uq_player_rank"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("section.id", ondelete="CASCADE"), index=True
    )
    start_rank: Mapped[int] = mapped_column(Integer())
    name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(8), default="")
    rating: Mapped[int | None] = mapped_column(Integer(), default=None)
    federation: Mapped[str] = mapped_column(String(8), default="")
    fide_id: Mapped[str] = mapped_column(String(16), default="")

    section: Mapped[Section] = relationship(back_populates="players")


class Round(Base):
    __tablename__ = "round"
    __table_args__ = (UniqueConstraint("section_id", "number", name="uq_round_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("section.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer())
    state: Mapped[RoundState] = mapped_column(
        _enum(RoundState, "round_state"), default=RoundState.OPEN
    )
    # The imported file, verbatim. Export re-serializes from this so that every
    # field we never modelled goes back to Vega unchanged.
    source_trf: Mapped[str] = mapped_column(Text())
    source_filename: Mapped[str] = mapped_column(String(255), default="")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    section: Mapped[Section] = relationship(back_populates="rounds")
    games: Mapped[list[Game]] = relationship(
        back_populates="round", cascade="all, delete-orphan", order_by="Game.board"
    )


class Game(Base):
    """One board in one round.

    Results are stored as the TRF codes themselves, one per side. Storing the
    pair rather than a single white-side code is what lets a double forfeit and
    a bye be expressed at all -- neither has a single-code form.
    """

    __tablename__ = "game"
    __table_args__ = (
        UniqueConstraint("round_id", "board", name="uq_game_board"),
        CheckConstraint(
            "(black_rank IS NULL) = (black_name IS NULL)", name="ck_game_black_consistent"
        ),
        CheckConstraint(
            "state <> 'confirmed' OR white_result <> ' '", name="ck_game_confirmed_has_result"
        ),
        CheckConstraint(
            "state <> 'empty' OR white_result = ' '", name="ck_game_empty_has_no_result"
        ),
        CheckConstraint("board > 0", name="ck_game_board_positive"),
        Index("ix_game_round_state", "round_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("round.id", ondelete="CASCADE"), index=True
    )
    board: Mapped[int] = mapped_column(Integer())

    white_rank: Mapped[int] = mapped_column(Integer())
    white_name: Mapped[str] = mapped_column(String(120))
    # NULL for a bye -- there is no opponent row in the file either.
    black_rank: Mapped[int | None] = mapped_column(Integer(), default=None)
    black_name: Mapped[str | None] = mapped_column(String(120), default=None)

    white_result: Mapped[str] = mapped_column(String(1), default=" ")
    black_result: Mapped[str] = mapped_column(String(1), default=" ")
    state: Mapped[ResultState] = mapped_column(
        _enum(ResultState, "result_state"), default=ResultState.EMPTY
    )
    # Set when a second, different claim arrives; kept so the arbiter can see
    # both sides of the disagreement rather than just the winner.
    disputed_white_result: Mapped[str | None] = mapped_column(String(1), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    round: Mapped[Round] = relationship(back_populates="games")


class GameEvent(Base):
    """Append-only audit log. Never updated, never deleted.

    Anchored to a natural key rather than a game id: an import rebuilds the
    section, so a surrogate id would be invalidated by exactly the event we
    most need to audit.
    """

    __tablename__ = "game_event"
    __table_args__ = (
        Index("ix_event_natural", "section_id", "round_number"),
        Index("ix_event_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("section.id", ondelete="CASCADE"), index=True
    )
    round_number: Mapped[int] = mapped_column(Integer())
    white_name: Mapped[str | None] = mapped_column(String(120), default=None)
    black_name: Mapped[str | None] = mapped_column(String(120), default=None)
    action: Mapped[EventAction] = mapped_column(_enum(EventAction, "event_action"))
    payload: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)

    actor_kind: Mapped[PrincipalKind] = mapped_column(_enum(PrincipalKind, "principal_kind"))
    actor_subject: Mapped[str] = mapped_column(String(255), default="")
    device_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Device(Base):
    """A phone or tablet admitted to one tournament for one playing day.

    App-issued, never through the IdP. The token is stored hashed, so a database
    read cannot mint access.
    """

    __tablename__ = "device"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournament.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120), default="")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    tournament: Mapped[Tournament] = relationship(back_populates="devices")


class IdempotencyRecord(Base):
    """One row per client-generated key, so an offline retry cannot double-submit."""

    __tablename__ = "idempotency_record"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    command: Mapped[str] = mapped_column(String(64))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
