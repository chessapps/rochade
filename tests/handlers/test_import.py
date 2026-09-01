from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.imports.import_round import ImportRound
from seebach.features.imports.preview_import import PreviewImport
from seebach.platform.errors import Conflict, ValidationFailed
from seebach.shared.enums import EventAction, ResultState, RoundState
from seebach.shared.models import Game, GameEvent, Round, Section, SectionPlayer, Tournament
from tests.conftest import Send

pytestmark = pytest.mark.db


def _import(
    send: Send,
    tournament: Tournament,
    content: str,
    name: str = "A",
    idempotency_key: str | None = None,
    **kw: object,
) -> object:
    return send(
        ImportRound(tournament_id=tournament.id, section_name=name, content=content, **kw),
        idempotency_key=idempotency_key,
    )


def test_preview_writes_nothing(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    plan = send(PreviewImport(tournament_id=tournament.id, section_name="A", content=round1_text))
    assert plan.file_round == 1
    assert plan.expected_round == 1
    assert plan.is_expected_round
    assert plan.boards == 4
    assert plan.byes == 0
    assert plan.players_total == 8
    assert len(plan.players_added) == 8
    assert plan.can_import

    assert session.scalars(select(Section)).all() == []


def test_import_creates_section_round_and_boards(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    result = _import(send, tournament, round1_text, filename="round1.trf")
    assert result.round_number == 1
    assert result.boards == 4

    section = session.scalars(select(Section)).one()
    assert section.name == "A"
    assert section.declared_rounds == 5
    assert len(section.players) == 8

    round_ = session.scalars(select(Round)).one()
    assert round_.state is RoundState.OPEN
    assert round_.source_filename == "round1.trf"
    # The file is kept verbatim so the export can patch it rather than rebuild.
    assert round_.source_trf == round1_text

    games = sorted(round_.games, key=lambda g: g.board)
    # FIDE board order: nobody has points in round 1, so the higher-ranked player decides.
    assert [(g.white_rank, g.black_rank) for g in games] == [(1, 5), (6, 2), (3, 7), (8, 4)]
    assert all(g.state is ResultState.EMPTY for g in games)
    assert games[0].white_name == "Baumann, Lukas"


def test_import_records_an_audit_event(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    _import(send, tournament, round1_text)
    event = session.scalars(select(GameEvent)).one()
    assert event.action is EventAction.ROUND_IMPORTED
    assert event.round_number == 1
    assert event.payload["boards"] == 4
    assert event.actor_subject == "arbiter@example.test"


def test_import_of_a_later_round_marks_earlier_rounds_history(
    send: Send, session: Session, tournament: Tournament, round3_text: str
) -> None:
    result = _import(send, tournament, round3_text)
    assert result.round_number == 3

    rounds = session.scalars(select(Round).order_by(Round.number)).all()
    assert [r.number for r in rounds] == [1, 2, 3]
    assert [r.state for r in rounds] == [
        RoundState.EXPORTED,
        RoundState.EXPORTED,
        RoundState.OPEN,
    ]

    played = [g for g in rounds[0].games if g.black_rank is not None]
    assert all(g.state is ResultState.CONFIRMED for g in played)
    assert all(g.state is ResultState.EMPTY for g in rounds[2].games if g.black_rank)


def test_byes_and_forfeits_survive_the_import(
    send: Send, session: Session, tournament: Tournament, round3_text: str
) -> None:
    _import(send, tournament, round3_text)
    rounds = {r.number: r for r in session.scalars(select(Round)).all()}

    byes = [g for g in rounds[1].games if g.black_rank is None]
    assert sorted(g.white_result for g in byes) == ["H", "U", "Z"]
    assert all(g.state is ResultState.CONFIRMED for g in byes)

    forfeit = next(g for g in rounds[2].games if g.white_rank == 5)
    assert (forfeit.white_result, forfeit.black_result) == ("+", "-")


def test_import_is_idempotent_under_a_repeated_key(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    first = _import(send, tournament, round1_text, idempotency_key="k-1")
    second = send(
        ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text),
        idempotency_key="k-1",
    )
    assert first.round_id == second.round_id
    assert session.scalar(select(Section).where(Section.name == "A")) is not None
    assert len(session.scalars(select(GameEvent)).all()) == 1


def test_a_file_with_no_players_is_rejected(send: Send, tournament: Tournament) -> None:
    with pytest.raises(ValidationFailed, match="no player rows"):
        _import(send, tournament, "012 Empty\r\nXXR 5\r\n")


def test_rounds_must_arrive_in_order(
    send: Send, tournament: Tournament, round3_text: str, round1_text: str
) -> None:
    _import(send, tournament, round1_text)
    trimmed = round3_text  # jumps from round 1 straight to round 3
    with pytest.raises(Conflict) as excinfo:
        _import(send, tournament, trimmed)
    assert "has not been imported yet" in str(excinfo.value.details["reasons"])


def test_sections_are_independent(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    _import(send, tournament, round1_text, name="A")
    _import(send, tournament, round1_text, name="B")
    assert len(session.scalars(select(Section)).all()) == 2
    assert len(session.scalars(select(SectionPlayer)).all()) == 16
    assert len(session.scalars(select(Game)).all()) == 8
