from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.devices.issue_device_token import IssueDeviceToken
from rochade.features.imports.import_round import ImportRound
from rochade.features.tournaments.delete_tournament import DeleteTournament
from rochade.features.tournaments.list_tournaments import ListTournaments
from rochade.platform.errors import Forbidden, ValidationFailed
from rochade.shared.models import Device, Game, GameEvent, Section, Tournament, TournamentMember
from tests.conftest import ARBITER, OWNER, Send

pytestmark = pytest.mark.db


def test_the_owner_can_delete_a_tournament_and_everything_under_it_goes(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    send(IssueDeviceToken(tournament_id=tournament.id, label="poster"))
    session.commit()
    assert session.scalars(select(Game)).first() is not None

    gone = send(
        DeleteTournament(tournament_id=tournament.id, confirm_name=tournament.name),
        principal=OWNER,
    )
    session.commit()

    assert gone.name == "Rochade Open 2026"
    assert session.get(Tournament, tournament.id) is None
    for model in (Section, Game, GameEvent, Device, TournamentMember):
        assert session.scalars(select(model)).first() is None, model.__name__
    assert send(ListTournaments(), principal=OWNER) == []


def test_the_name_must_be_typed_back_exactly(
    send: Send, session: Session, tournament: Tournament
) -> None:
    with pytest.raises(ValidationFailed, match="does not match"):
        send(
            DeleteTournament(tournament_id=tournament.id, confirm_name="Rochade Open"),
            principal=OWNER,
        )
    session.rollback()
    assert session.get(Tournament, tournament.id) is not None


def test_an_arbiter_cannot_delete_a_tournament(
    send: Send, session: Session, tournament: Tournament
) -> None:
    with pytest.raises(Forbidden):
        send(
            DeleteTournament(tournament_id=tournament.id, confirm_name=tournament.name),
            principal=ARBITER,
        )
    session.rollback()
    assert session.get(Tournament, tournament.id) is not None
