"""Staff sign-in through an OIDC issuer.

No Zitadel here: a key pair made for the test signs the tokens, and the JWKS
fetch is stubbed to hand out its public half. What is under test is the edge
-- issuer, audience, expiry, key rotation, and the boundary with dev auth.
"""

from __future__ import annotations

import json
import pathlib
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rochade.app import create_app
from rochade.platform.auth import oidc
from rochade.platform.config import Settings, settings
from rochade.platform.db import get_session

pytestmark = pytest.mark.db

ISSUER = "http://auth.test:8093"
CLIENT_ID = "123456@rochade"


class Signer:
    def __init__(self, kid: str) -> None:
        self.kid = kid
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        public_pem = (
            key.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode()
        )
        public = jwk.construct(public_pem, algorithm="RS256").to_dict()
        public["kid"] = kid
        self.jwk = public

    def token(self, **overrides: Any) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "sub": "224466",
            "aud": [CLIENT_ID, "999@rochade"],
            "exp": now + 300,
            "iat": now,
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_pem, algorithm="RS256", headers={"kid": self.kid})


@pytest.fixture
def signer() -> Signer:
    return Signer("key-1")


@pytest.fixture
def jwks(signer: Signer, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The key set the issuer would publish; tests may swap its keys."""
    published = {"keys": [signer.jwk]}
    monkeypatch.setattr(oidc, "_fetch_jwks", lambda config: json.loads(json.dumps(published)))
    oidc.reset_cache()
    return published


@pytest.fixture
def client(
    engine: Engine, session: Session, monkeypatch: pytest.MonkeyPatch, jwks: dict[str, Any]
) -> Iterator[TestClient]:
    monkeypatch.delenv("ROCHADE_DEV_AUTH_ENABLED", raising=False)
    monkeypatch.setenv("ROCHADE_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("ROCHADE_OIDC_CLIENT_ID", CLIENT_ID)
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
    oidc.reset_cache()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_the_browser_is_told_where_to_sign_in(client: TestClient) -> None:
    assert client.get("/api/auth/config").json() == {
        "issuer": ISSUER,
        "client_id": CLIENT_ID,
        "dev_auth": False,
        "device_join": False,
    }


def test_a_token_from_the_issuer_is_a_staff_account(client: TestClient, signer: Signer) -> None:
    created = client.post(
        "/api/tournaments",
        json={"name": "OIDC Open", "manager": "vega"},
        headers=bearer(signer.token()),
    )
    assert created.status_code == 201, created.text
    listed = client.get("/api/tournaments", headers=bearer(signer.token())).json()
    assert [t["name"] for t in listed] == ["OIDC Open"]
    # The subject is the issuer's `sub`, so a second user sees nothing of it.
    other = client.get("/api/tournaments", headers=bearer(signer.token(sub="778899"))).json()
    assert other == []


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"aud": "someone-else"}, "audience"),
        ({"iss": "http://elsewhere.test"}, "issuer"),
        ({"exp": int(time.time()) - 10}, "expired"),
    ],
)
def test_wrong_tokens_are_rejected(
    client: TestClient, signer: Signer, overrides: dict[str, Any], reason: str
) -> None:
    response = client.get("/api/tournaments", headers=bearer(signer.token(**overrides)))
    assert response.status_code == 401, reason
    assert response.json()["code"] == "unauthenticated"


def test_a_token_signed_by_someone_else_is_rejected(client: TestClient) -> None:
    stranger = Signer("key-1")  # same kid, different key
    response = client.get("/api/tournaments", headers=bearer(stranger.token()))
    assert response.status_code == 401


def test_a_bare_token_is_not_a_subject_when_oidc_is_on(client: TestClient) -> None:
    response = client.get("/api/tournaments", headers=bearer("arbiter@example.test"))
    assert response.status_code == 401


def test_a_rotated_key_is_fetched_without_a_restart(
    client: TestClient, signer: Signer, jwks: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(oidc, "REFETCH_INTERVAL", 0.0)
    assert client.get("/api/tournaments", headers=bearer(signer.token())).status_code == 200
    rotated = Signer("key-2")
    jwks["keys"] = [rotated.jwk]
    assert client.get("/api/tournaments", headers=bearer(rotated.token())).status_code == 200
    # The old key is gone from the set now, so its tokens stop working.
    assert client.get("/api/tournaments", headers=bearer(signer.token())).status_code == 401


def test_unknown_key_ids_do_not_hammer_the_issuer(
    client: TestClient, signer: Signer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kid is read before the signature is checked, so anyone can pick it."""
    fetches = 0
    published = {"keys": [signer.jwk]}

    def counting(config: Settings) -> dict[str, Any]:
        nonlocal fetches
        fetches += 1
        return published

    monkeypatch.setattr(oidc, "_fetch_jwks", counting)
    oidc.reset_cache()
    assert client.get("/api/tournaments", headers=bearer(signer.token())).status_code == 200
    for i in range(20):
        stranger = Signer(f"made-up-{i}")
        assert client.get("/api/tournaments", headers=bearer(stranger.token())).status_code == 401
    assert fetches == 1
    # The genuine key is still served from the cache meanwhile.
    assert client.get("/api/tournaments", headers=bearer(signer.token())).status_code == 200


def test_an_unreachable_issuer_is_a_401_not_a_crash(
    client: TestClient, signer: Signer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(config: Settings) -> dict[str, Any]:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(oidc, "_fetch_jwks", down)
    oidc.reset_cache()
    response = client.get("/api/tournaments", headers=bearer(signer.token()))
    assert response.status_code == 401
    assert "sign-in service" in response.json()["message"]


def test_no_audience_fails_closed(
    client: TestClient, signer: Signer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a client id any client of the issuer could sign in here."""
    monkeypatch.delenv("ROCHADE_OIDC_CLIENT_ID")
    settings.cache_clear()
    response = client.get("/api/tournaments", headers=bearer(signer.token()))
    assert response.status_code == 401
    assert "misconfigured" in response.json()["message"]


def test_dev_auth_beside_oidc_takes_plain_tokens_only(
    client: TestClient, signer: Signer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scripts sign in with a bare token; a bad JWT must not become one."""
    monkeypatch.setenv("ROCHADE_DEV_AUTH_ENABLED", "true")
    settings.cache_clear()
    assert client.get("/api/auth/config").json()["dev_auth"] is True
    assert client.get("/api/tournaments", headers=bearer("smoke-arbiter")).status_code == 200
    assert client.get("/api/tournaments", headers=bearer(signer.token())).status_code == 200
    forged = signer.token(iss="http://elsewhere.test")
    assert client.get("/api/tournaments", headers=bearer(forged)).status_code == 401


def test_the_setup_file_fills_what_the_environment_left_blank(tmp_path: pathlib.Path) -> None:
    written = tmp_path / "oidc.json"
    written.write_text(json.dumps({"issuer": ISSUER, "client_id": CLIENT_ID, "project_id": "1"}))
    config = Settings(oidc_config_file=str(written)).with_oidc_file()
    assert (config.oidc_issuer, config.oidc_client_id) == (ISSUER, CLIENT_ID)
    assert config.token_audience == CLIENT_ID

    pinned = Settings(oidc_config_file=str(written), oidc_issuer="http://pinned").with_oidc_file()
    assert pinned.oidc_issuer == "http://pinned"
    assert pinned.oidc_client_id == CLIENT_ID

    absent = Settings(oidc_config_file=str(tmp_path / "missing.json")).with_oidc_file()
    assert absent.oidc_enabled is False


def test_issuer_requests_go_inside_the_stack_with_the_public_host() -> None:
    config = Settings(
        oidc_issuer="https://auth.example.com", oidc_internal_url="http://zitadel:8080"
    )
    url, headers = oidc.issuer_request(config, oidc.jwks_url(config))
    assert url == "http://zitadel:8080/oauth/v2/keys"
    assert headers == {"Host": "auth.example.com"}

    with_port = Settings(
        oidc_issuer="http://localhost:8093", oidc_internal_url="http://zitadel:8080"
    )
    url, headers = oidc.issuer_request(with_port, oidc.jwks_url(with_port))
    assert (url, headers) == ("http://zitadel:8080/oauth/v2/keys", {"Host": "localhost:8093"})

    direct = Settings(oidc_issuer="https://auth.example.com")
    assert oidc.issuer_request(direct, oidc.jwks_url(direct)) == (
        "https://auth.example.com/oauth/v2/keys",
        {},
    )
