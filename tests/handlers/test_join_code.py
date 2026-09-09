"""Joining a tournament with a typed code instead of a scanned QR."""

from __future__ import annotations

import pytest

from rochade.features.boards.get_board_list import GetBoardList
from rochade.features.devices.join_code import ALPHABET, LENGTH, SetJoinCode
from rochade.features.devices.join_device import JoinDevice
from rochade.features.tournaments.get_tournament import GetTournament
from rochade.platform.config import settings
from rochade.platform.errors import NotFound, ValidationFailed
from rochade.platform.http import ANONYMOUS
from rochade.platform.mediator import Principal
from rochade.shared.enums import PrincipalKind
from rochade.shared.models import Tournament
from tests.conftest import ARBITER, Send

pytestmark = pytest.mark.db


@pytest.fixture
def joining_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROCHADE_DEVICE_JOIN_ENABLED", "true")
    settings.cache_clear()
    yield
    settings.cache_clear()


def test_the_arbiter_opens_and_closes_joining(send: Send, tournament: Tournament) -> None:
    opened = send(SetJoinCode(tournament_id=tournament.id))

    assert opened.join_code is not None
    assert len(opened.join_code) == LENGTH
    assert set(opened.join_code) <= set(ALPHABET)
    # Nothing that could be misread across a hall.
    assert not set(opened.join_code) & set("IO01")

    detail = send(GetTournament(tournament_id=tournament.id), principal=ARBITER)
    assert detail.join_code == opened.join_code

    rotated = send(SetJoinCode(tournament_id=tournament.id))
    assert rotated.join_code != opened.join_code

    closed = send(SetJoinCode(tournament_id=tournament.id, enabled=False))
    assert closed.join_code is None


def test_a_phone_joins_with_the_code_and_can_read_the_boards(
    send: Send, tournament: Tournament, joining_on: None
) -> None:
    code = send(SetJoinCode(tournament_id=tournament.id)).join_code
    assert code is not None

    joined = send(JoinDevice(code=code.lower()), principal=ANONYMOUS)

    assert joined.tournament_id == tournament.id
    assert joined.tournament_name == tournament.name

    boards = send(
        GetBoardList(tournament_id=tournament.id),
        principal=Principal(
            kind=PrincipalKind.DEVICE,
            subject=f"device:{joined.device_id}",
            device_id=joined.device_id,
            tournament_id=tournament.id,
        ),
    )
    assert boards is not None


def test_spaces_and_case_in_what_someone_typed_do_not_matter(
    send: Send, tournament: Tournament, joining_on: None
) -> None:
    code = send(SetJoinCode(tournament_id=tournament.id)).join_code
    assert code is not None
    typed = f" {code[:3].lower()}-{code[3:].lower()} "

    joined = send(JoinDevice(code=typed), principal=ANONYMOUS)

    assert joined.tournament_id == tournament.id


def test_each_phone_gets_its_own_device(
    send: Send, tournament: Tournament, joining_on: None
) -> None:
    """So the audit log still says which phone, and one can be revoked alone."""
    code = send(SetJoinCode(tournament_id=tournament.id)).join_code
    assert code is not None

    first = send(JoinDevice(code=code), principal=ANONYMOUS)
    second = send(JoinDevice(code=code, label="wall"), principal=ANONYMOUS)

    assert first.device_id != second.device_id
    assert first.token != second.token
    assert second.label == "wall"


def test_a_closed_code_opens_nothing(send: Send, tournament: Tournament, joining_on: None) -> None:
    code = send(SetJoinCode(tournament_id=tournament.id)).join_code
    assert code is not None
    send(SetJoinCode(tournament_id=tournament.id, enabled=False))

    with pytest.raises(NotFound):
        send(JoinDevice(code=code), principal=ANONYMOUS)


def test_a_wrong_code_says_nothing_useful(
    send: Send, tournament: Tournament, joining_on: None
) -> None:
    send(SetJoinCode(tournament_id=tournament.id))

    with pytest.raises(NotFound) as caught:
        send(JoinDevice(code="ZZZZZZ"), principal=ANONYMOUS)

    assert "does not open anything" in str(caught.value)


def test_joining_is_off_unless_asked_for(send: Send, tournament: Tournament) -> None:
    """An unauthenticated way to mint access must be opted into, never inherited."""
    settings.cache_clear()
    code = send(SetJoinCode(tournament_id=tournament.id)).join_code
    assert code is not None

    with pytest.raises(ValidationFailed) as caught:
        send(JoinDevice(code=code), principal=ANONYMOUS)

    assert "switched off" in str(caught.value)
