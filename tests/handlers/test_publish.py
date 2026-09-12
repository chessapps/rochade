"""Publishing a tournament: off by default, a slug from the name, arbiter only."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from rochade.features.tournaments.get_tournament import GetTournament
from rochade.features.tournaments.publish_tournament import PublishTournament, slugify
from rochade.platform.errors import Forbidden, ValidationFailed
from rochade.platform.mediator import Principal
from rochade.shared.enums import PrincipalKind, Role
from rochade.shared.models import Tournament, TournamentMember
from tests.conftest import ARBITER, Send

pytestmark = pytest.mark.db


def test_a_new_tournament_is_not_public(send: Send, tournament: Tournament) -> None:
    detail = send(GetTournament(tournament_id=tournament.id), principal=ARBITER)
    assert detail.published is False
    assert detail.slug is None


def test_publishing_gives_a_slug_from_the_name_and_keeps_it(
    send: Send, tournament: Tournament
) -> None:
    shown = send(PublishTournament(tournament_id=tournament.id, published=True))
    assert (shown.published, shown.slug) == (True, "rochade-open-2026")

    hidden = send(PublishTournament(tournament_id=tournament.id, published=False))
    assert (hidden.published, hidden.slug) == (False, "rochade-open-2026")

    detail = send(GetTournament(tournament_id=tournament.id), principal=ARBITER)
    assert (detail.published, detail.slug) == (False, "rochade-open-2026")


def test_a_second_tournament_with_the_same_name_gets_a_numbered_slug(
    send: Send, tournament: Tournament, session: Session
) -> None:
    send(PublishTournament(tournament_id=tournament.id, published=True))
    other = Tournament(name=tournament.name, manager="vega")
    session.add(other)
    session.flush()
    session.add(
        TournamentMember(tournament_id=other.id, subject=ARBITER.subject, role=Role.ARBITER)
    )
    session.commit()

    result = send(PublishTournament(tournament_id=other.id, published=True))
    assert result.slug == "rochade-open-2026-2"


def test_the_arbiter_may_choose_the_slug_but_not_one_in_use(
    send: Send, tournament: Tournament, session: Session
) -> None:
    other = Tournament(name="Other", manager="vega", slug="taken", published=True)
    session.add(other)
    session.commit()

    chosen = send(PublishTournament(tournament_id=tournament.id, published=True, slug="open-a"))
    assert chosen.slug == "open-a"

    with pytest.raises(ValidationFailed, match="already uses"):
        send(PublishTournament(tournament_id=tournament.id, published=True, slug="taken"))
    with pytest.raises(ValidationFailed, match="lower-case"):
        send(PublishTournament(tournament_id=tournament.id, published=True, slug="Open A"))


def test_a_device_cannot_publish(send: Send, tournament: Tournament) -> None:
    device = Principal(kind=PrincipalKind.DEVICE, subject="device", tournament_id=tournament.id)
    with pytest.raises(Forbidden):
        send(PublishTournament(tournament_id=tournament.id, published=True), principal=device)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Zürich Open 2026", "zurich-open-2026"),
        ("  Café -- Blitz!  ", "cafe-blitz"),
        ("東京", ""),
    ],
)
def test_slugify(name: str, slug: str) -> None:
    assert slugify(name) == slug
