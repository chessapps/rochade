"""The HTTP edge: authentication, error translation, and one end-to-end path.

Handler tests cover behaviour; these cover the things only the edge can get
wrong -- turning a credential into a principal, and turning a domain error into
a status code.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rochade.app import create_app
from rochade.platform.config import settings
from rochade.platform.db import get_session
from tests.conftest import ARBITER, OWNER

pytestmark = pytest.mark.db


@pytest.fixture
def client(
    engine: Engine, session: Session, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    # Dev auth is off by default, so the edge tests turn it on explicitly --
    # which is also a test that it is genuinely off until asked for.
    monkeypatch.setenv("ROCHADE_DEV_AUTH_ENABLED", "true")
    # Startup migrates whatever ROCHADE_DATABASE_URL names; make that the
    # throwaway database, never the developer's own.
    monkeypatch.setenv("ROCHADE_DATABASE_URL", engine.url.render_as_string(hide_password=False))
    settings.cache_clear()
    app = create_app()
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    def override() -> Iterator[Session]:
        with factory() as opened:
            yield opened

    app.dependency_overrides[get_session] = override
    with TestClient(app) as built:
        yield built
    settings.cache_clear()


def staff(subject: str = ARBITER.subject) -> dict[str, str]:
    return {"Authorization": f"Bearer {subject}"}


def test_health_needs_no_credentials(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_credentials_are_rejected(client: TestClient) -> None:
    response = client.get("/api/tournaments")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_a_malformed_authorization_header_is_rejected(client: TestClient) -> None:
    response = client.get("/api/tournaments", headers={"Authorization": "Bearer   "})
    assert response.status_code == 401


def test_an_unsupported_scheme_is_rejected(client: TestClient) -> None:
    response = client.get("/api/tournaments", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401
    assert "unsupported" in response.json()["message"]


def test_an_unknown_device_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/tournaments/00000000-0000-0000-0000-000000000000/boards",
        headers={"Authorization": "Device nonsense"},
    )
    assert response.status_code == 401
    assert response.json()["message"] == "unknown device token"


def test_the_whole_flow_over_http(client: TestClient, round1_text: str) -> None:
    created = client.post(
        "/api/tournaments",
        json={"name": "HTTP Open", "city": "Rochade", "manager": "vega"},
        headers=staff(OWNER.subject),
    )
    assert created.status_code == 201
    tournament_id = created.json()["id"]

    preview = client.post(
        f"/api/tournaments/{tournament_id}/imports/preview",
        json={"section_name": "A", "content": round1_text},
        headers=staff(OWNER.subject),
    )
    assert preview.status_code == 200
    assert preview.json()["boards"] == 4

    imported = client.post(
        f"/api/tournaments/{tournament_id}/imports",
        json={"section_name": "A", "content": round1_text, "filename": "r1.trf"},
        headers=staff(OWNER.subject),
    )
    assert imported.status_code == 201
    round_id = imported.json()["round_id"]

    issued = client.post(
        f"/api/tournaments/{tournament_id}/devices",
        json={"label": "phone", "base_url": "https://rochade.example"},
        headers=staff(OWNER.subject),
    )
    assert issued.status_code == 201
    token = issued.json()["token"]
    phone = {"Authorization": f"Device {token}"}

    boards = client.get(f"/api/tournaments/{tournament_id}/boards", headers=phone)
    assert boards.status_code == 200
    listing = boards.json()["boards"]
    assert len(listing) == 4

    for board in listing:
        claimed = client.post(
            f"/api/games/{board['game_id']}/claim",
            json={"result": "white_win"},
            headers={**phone, "Idempotency-Key": f"claim-{board['game_id']}"},
        )
        assert claimed.status_code == 200
        assert claimed.json()["state"] == "claimed"

    # A phone may not release.
    assert client.post(f"/api/rounds/{round_id}/release", json={}, headers=phone).status_code == 403

    released = client.post(f"/api/rounds/{round_id}/release", json={}, headers=staff(OWNER.subject))
    assert released.status_code == 200
    assert released.json()["confirmed"] == 4

    exported = client.post(f"/api/rounds/{round_id}/export", json={}, headers=staff(OWNER.subject))
    assert exported.status_code == 200
    body = exported.json()
    assert body["filename"] == "A.trf"
    assert body["boards_written"] == 4

    from rochade.trf import parse

    assert parse(body["content"]).player(1).round(1).result == "1"


def test_a_revoked_device_loses_access_immediately(client: TestClient, round1_text: str) -> None:
    tournament_id = client.post(
        "/api/tournaments", json={"name": "Revocation", "manager": "vega"}, headers=staff()
    ).json()["id"]
    client.post(
        f"/api/tournaments/{tournament_id}/imports",
        json={"section_name": "A", "content": round1_text},
        headers=staff(),
    )
    issued = client.post(
        f"/api/tournaments/{tournament_id}/devices", json={}, headers=staff()
    ).json()
    phone = {"Authorization": f"Device {issued['token']}"}

    assert client.get(f"/api/tournaments/{tournament_id}/boards", headers=phone).status_code == 200
    # Removing is not a way to revoke.
    assert client.delete(f"/api/devices/{issued['device_id']}", headers=staff()).status_code == 409
    client.post(f"/api/devices/{issued['device_id']}/revoke", headers=staff())

    denied = client.get(f"/api/tournaments/{tournament_id}/boards", headers=phone)
    assert denied.status_code == 401
    assert "revoked" in denied.json()["message"]

    assert client.delete(f"/api/devices/{issued['device_id']}", headers=staff()).status_code == 200
    assert client.get(f"/api/tournaments/{tournament_id}/devices", headers=staff()).json() == []


def test_a_conflict_becomes_a_409(client: TestClient, round1_text: str) -> None:
    tournament_id = client.post(
        "/api/tournaments", json={"name": "Conflicts", "manager": "vega"}, headers=staff()
    ).json()["id"]
    imported = client.post(
        f"/api/tournaments/{tournament_id}/imports",
        json={"section_name": "A", "content": round1_text},
        headers=staff(),
    ).json()

    response = client.post(f"/api/rounds/{imported['round_id']}/release", json={}, headers=staff())
    assert response.status_code == 409
    assert response.json()["details"]["empty_boards"] == [1, 2, 3, 4]


def test_the_public_reads_a_published_tournament_without_credentials(
    client: TestClient, round1_text: str
) -> None:
    created = client.post(
        "/api/tournaments", json={"name": "Open", "manager": "vega"}, headers=staff(OWNER.subject)
    ).json()
    client.post(
        f"/api/tournaments/{created['id']}/imports",
        json={"section_name": "A", "content": round1_text},
        headers=staff(OWNER.subject),
    )

    assert client.get("/api/public/tournaments/open").status_code == 404
    assert client.get("/api/public/tournaments").json() == []

    shown = client.put(
        f"/api/tournaments/{created['id']}/publication",
        json={"published": True},
        headers=staff(OWNER.subject),
    )
    assert shown.status_code == 200, shown.text
    assert shown.json() == {"published": True, "slug": "open"}

    answer = client.get("/api/public/tournaments/open")
    assert answer.status_code == 200
    assert answer.headers["Cache-Control"] == "public, max-age=15"
    section = answer.json()["sections"][0]
    boards = client.get(f"/api/public/tournaments/open/sections/{section['id']}/rounds/1")
    assert boards.status_code == 200
    assert len(boards.json()["boards"]) == 4


def test_dev_auth_is_off_unless_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """An insecure auth mode must be opted into, never inherited."""
    monkeypatch.delenv("ROCHADE_DEV_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("ROCHADE_OIDC_ISSUER", raising=False)
    monkeypatch.setenv("ROCHADE_MIGRATE_ON_START", "false")
    settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/api/tournaments", headers=staff())
        assert response.status_code == 401
        assert "not configured" in response.json()["message"]
    finally:
        settings.cache_clear()
