from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from seebach.features.devices.issue_device_token import IssueDeviceToken
from seebach.features.devices.list_devices import ListDevices
from seebach.features.devices.remove_device import RemoveDevice
from seebach.features.devices.revoke_device import RevokeDevice
from seebach.features.imports.import_round import ImportRound
from seebach.platform.auth.principal import current_principal
from seebach.platform.auth.tokens import hash_token, mint
from seebach.platform.errors import Conflict, Forbidden, NotFound, Unauthenticated
from seebach.platform.mediator import Principal
from seebach.shared.enums import EventAction, PrincipalKind
from seebach.shared.models import Device, GameEvent, Tournament
from tests.conftest import Send

pytestmark = pytest.mark.db


def test_a_token_is_stored_only_as_a_hash(
    send: Send, session: Session, tournament: Tournament
) -> None:
    issued = send(IssueDeviceToken(tournament_id=tournament.id, label="phone by board 1"))

    device = session.scalars(select(Device)).one()
    assert device.token_hash == hash_token(issued.token)
    assert issued.token not in device.token_hash
    # Nothing anywhere holds the token itself; it is shown once and that is all.
    assert device.token_hash != issued.token


def test_the_qr_payload_carries_the_tournament_and_the_token(
    send: Send, tournament: Tournament
) -> None:
    issued = send(
        IssueDeviceToken(tournament_id=tournament.id, base_url="https://seebach.example/")
    )
    assert issued.qr_payload == f"https://seebach.example/hall/{tournament.id}#t={issued.token}"


def test_a_token_works_until_it_is_revoked(
    send: Send, session: Session, tournament: Tournament
) -> None:
    """No clock ever kills a token: a poster must still work on day three."""
    issued = send(IssueDeviceToken(tournament_id=tournament.id))
    session.commit()

    admitted = current_principal(f"Device {issued.token}", session)
    assert admitted.device_id == issued.device_id
    assert not hasattr(issued, "expires_at")

    send(RevokeDevice(device_id=issued.device_id))
    session.commit()
    with pytest.raises(Unauthenticated):
        current_principal(f"Device {issued.token}", session)


def test_minting_never_repeats(send: Send, tournament: Tournament) -> None:
    tokens = {send(IssueDeviceToken(tournament_id=tournament.id)).token for _ in range(5)}
    assert len(tokens) == 5
    assert len({mint()[0] for _ in range(50)}) == 50


def test_issuing_is_audited_once_the_tournament_has_a_section(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    send(IssueDeviceToken(tournament_id=tournament.id, label="tablet"))

    event = session.scalars(
        select(GameEvent).where(GameEvent.action == EventAction.DEVICE_ISSUED)
    ).one()
    assert event.payload["label"] == "tablet"


def test_revoking_is_idempotent(send: Send, session: Session, tournament: Tournament) -> None:
    issued = send(IssueDeviceToken(tournament_id=tournament.id))
    first = send(RevokeDevice(device_id=issued.device_id))
    second = send(RevokeDevice(device_id=issued.device_id))
    assert first.revoked_at == second.revoked_at

    device = session.scalars(select(Device)).one()
    assert device.revoked_at is not None


def test_listing_devices_reports_which_are_still_usable(send: Send, tournament: Tournament) -> None:
    live = send(IssueDeviceToken(tournament_id=tournament.id, label="live"))
    revoked = send(IssueDeviceToken(tournament_id=tournament.id, label="revoked"))
    send(RevokeDevice(device_id=revoked.device_id))

    listed = {d.label: d for d in send(ListDevices(tournament_id=tournament.id))}
    assert listed["live"].active
    assert not listed["revoked"].active
    assert listed["live"].id == live.device_id


def test_a_revoked_device_can_be_removed_and_its_history_stays(
    send: Send, session: Session, tournament: Tournament, round1_text: str
) -> None:
    send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))
    issued = send(IssueDeviceToken(tournament_id=tournament.id, label="old poster"))
    send(RevokeDevice(device_id=issued.device_id))

    send(RemoveDevice(device_id=issued.device_id))

    assert send(ListDevices(tournament_id=tournament.id)) == []
    actions = [
        e.action
        for e in session.scalars(select(GameEvent).order_by(GameEvent.created_at)).all()
        if e.payload.get("device") == str(issued.device_id)
    ]
    assert actions == [
        EventAction.DEVICE_ISSUED,
        EventAction.DEVICE_REVOKED,
        EventAction.DEVICE_REMOVED,
    ]


def test_a_working_device_cannot_be_removed(send: Send, tournament: Tournament) -> None:
    """Removing is tidying, never a back door around revoke."""
    issued = send(IssueDeviceToken(tournament_id=tournament.id))
    with pytest.raises(Conflict):
        send(RemoveDevice(device_id=issued.device_id))
    assert send(ListDevices(tournament_id=tournament.id))[0].active


def test_a_device_cannot_issue_or_revoke_devices(send: Send, tournament: Tournament) -> None:
    phone = Principal(
        kind=PrincipalKind.DEVICE,
        subject="device:phone",
        device_id=uuid.uuid4(),
        tournament_id=tournament.id,
    )
    with pytest.raises(Forbidden):
        send(IssueDeviceToken(tournament_id=tournament.id), principal=phone)


def test_issuing_for_an_unknown_tournament_is_not_found(send: Send) -> None:
    with pytest.raises((NotFound, Forbidden)):
        send(IssueDeviceToken(tournament_id=uuid.uuid4()))
