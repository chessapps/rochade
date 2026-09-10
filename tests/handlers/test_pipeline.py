"""The mediator pipeline itself."""

from __future__ import annotations

import logging
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rochade.features.tournaments.create_tournament import CreateTournament
from rochade.platform.errors import Forbidden, IdempotencyConflict
from rochade.shared.models import IdempotencyRecord, Tournament
from tests.conftest import Send

pytestmark = pytest.mark.db


def test_every_message_is_logged_at_info(send: Send, caplog: pytest.LogCaptureFixture) -> None:
    """Reserved LogRecord names in `extra` raise rather than being ignored.

    Only reachable when the logger is actually enabled, which is why this test
    turns it on explicitly instead of trusting the default level.
    """
    with caplog.at_level(logging.INFO, logger="rochade.mediator"):
        send(CreateTournament(name="Logged", manager="vega"))

    record = next(r for r in caplog.records if r.name == "rochade.mediator")
    assert record.rochade_message == "CreateTournament"  # type: ignore[attr-defined]
    assert record.rochade_outcome == "ok"  # type: ignore[attr-defined]
    assert record.getMessage() == "CreateTournament ok"


def test_a_rejection_is_logged_too(send: Send, caplog: pytest.LogCaptureFixture) -> None:
    """A round nobody can resolve a tournament for is forbidden, not not-found.

    Authorization runs before the handler, so an id that does not exist and one
    the caller may not see are indistinguishable from outside -- which is the
    behaviour we want, and it is still logged.
    """
    from rochade.features.rounds.release_round import ReleaseRound

    with caplog.at_level(logging.INFO, logger="rochade.mediator"), pytest.raises(Forbidden):
        send(ReleaseRound(round_id=uuid.uuid4()))

    record = next(r for r in caplog.records if r.name == "rochade.mediator")
    assert record.rochade_outcome == "forbidden"  # type: ignore[attr-defined]


def test_a_failed_command_leaves_nothing_behind(send: Send, session: Session) -> None:
    from rochade.features.imports.import_round import ImportRound
    from rochade.platform.errors import ValidationFailed

    created = send(CreateTournament(name="Rollback", manager="vega"))
    with pytest.raises(ValidationFailed):
        send(ImportRound(tournament_id=created.id, section_name="A", content="012 Nothing\r\n"))

    session.rollback()
    assert session.scalars(select(Tournament)).all() != []
    from rochade.shared.models import Section

    assert session.scalars(select(Section)).all() == []


def test_reusing_a_key_for_a_different_request_is_a_conflict(send: Send) -> None:
    send(CreateTournament(name="First", manager="vega"), idempotency_key="shared")
    with pytest.raises(IdempotencyConflict):
        send(CreateTournament(name="Second", manager="vega"), idempotency_key="shared")


def test_the_dedupe_record_commits_with_the_command(send: Send, session: Session) -> None:
    send(CreateTournament(name="Together", manager="vega"), idempotency_key="k")
    record = session.get(IdempotencyRecord, "k")
    assert record is not None
    assert record.command == "CreateTournament"
    assert record.response["name"] == "Together"


def test_a_replay_returns_the_same_type_not_a_dict(send: Send) -> None:
    first = send(CreateTournament(name="Typed", manager="vega"), idempotency_key="typed")
    replay = send(CreateTournament(name="Typed", manager="vega"), idempotency_key="typed")
    assert type(replay) is type(first)
    assert replay.id == first.id
