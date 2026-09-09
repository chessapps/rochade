from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rochade.platform.bus import bus
from rochade.platform.config import Settings
from rochade.platform.mediator import Context, Message, Principal
from rochade.platform.migrate import upgrade_to_head
from rochade.shared.enums import PrincipalKind, Role
from rochade.shared.models import Base, Tournament, TournamentMember

ROOT = pathlib.Path(__file__).resolve().parents[1]

# A developer's .env names their own database and switches dev auth on. The
# tests set what they need explicitly and must never inherit either.
Settings.model_config["env_file"] = None
FIXTURES = pathlib.Path(__file__).parent / "fixtures"

ARBITER = Principal(kind=PrincipalKind.STAFF, subject="arbiter@example.test")
OWNER = Principal(kind=PrincipalKind.STAFF, subject="owner@example.test")


# --- TRF fixtures (no database needed) --------------------------------------


@pytest.fixture
def fixtures_dir() -> pathlib.Path:
    return FIXTURES


@pytest.fixture
def round1_text() -> str:
    return (FIXTURES / "round1_pairings.trf").read_bytes().decode("utf-8")


@pytest.fixture
def round3_text() -> str:
    return (FIXTURES / "round3_messy.trf").read_bytes().decode("utf-8")


# --- database ---------------------------------------------------------------


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A throwaway Postgres for the session.

    Managed with the docker CLI directly rather than through a container
    library: the whole need is one image, one mapped port and a readiness
    check, and doing it explicitly means a failure says which of those broke.

    Set ROCHADE_TEST_DATABASE_URL to point at an existing database instead.
    """
    override = os.environ.get("ROCHADE_TEST_DATABASE_URL")
    if override:
        yield override
        return

    if shutil.which("docker") is None:  # pragma: no cover - environment guard
        pytest.skip("docker is not available and ROCHADE_TEST_DATABASE_URL is not set")

    name = f"rochade-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-e",
            "POSTGRES_USER=rochade",
            "-e",
            "POSTGRES_PASSWORD=rochade",
            "-e",
            "POSTGRES_DB=rochade",
            "-p",
            "5432",
            "postgres:16-alpine",
            "-c",
            "fsync=off",
            "-c",
            "full_page_writes=off",
        ],
        check=True,
        capture_output=True,
    )
    try:
        port = _mapped_port(name)
        url = f"postgresql+psycopg://rochade:rochade@127.0.0.1:{port}/rochade"
        _await_ready(name, url)
        yield url
    finally:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)


def _mapped_port(name: str) -> int:
    output = subprocess.run(
        ["docker", "port", name, "5432/tcp"], check=True, capture_output=True, text=True
    ).stdout
    # Docker lists one line per address family; any of them maps the same port.
    return int(output.strip().splitlines()[0].rsplit(":", 1)[1])


def _await_ready(name: str, url: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    probe = create_engine(url, future=True, connect_args={"connect_timeout": 2})
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with probe.connect() as connection:
                connection.execute(text("SELECT 1"))
            probe.dispose()
            return
        except Exception as exc:
            last = exc
            time.sleep(0.5)
    probe.dispose()
    raise RuntimeError(f"postgres container {name} never became ready: {last}")


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """Schema comes from Alembic, not `create_all`.

    That way every handler test is also a test that the migration produces the
    schema the code expects -- the two drifting apart is otherwise only found
    on a deploy.
    """
    upgrade_to_head(database_url)

    built = create_engine(database_url, future=True)
    yield built
    built.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as opened:
        yield opened


Send = Callable[..., Any]


@pytest.fixture
def send(session: Session) -> Send:
    """Dispatch a message through the real pipeline, bypassing HTTP.

    Handler tests are the main tier: one file per use case makes the use case
    the natural unit, and going through the mediator means authorization,
    validation, transactions and idempotency are exercised too.
    """

    def dispatch(
        message: Message,
        *,
        principal: Principal = ARBITER,
        idempotency_key: str | None = None,
        ip: str | None = "203.0.113.7",
        user_agent: str | None = "pytest",
    ) -> Any:
        ctx = Context(
            session=session,
            principal=principal,
            request_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            ip=ip,
            user_agent=user_agent,
        )
        return bus.send(message, ctx)

    return dispatch


@pytest.fixture
def tournament(session: Session) -> Tournament:
    created = Tournament(name="Rochade Open 2026", city="Rochade", federation="SUI")
    session.add(created)
    session.flush()
    session.add_all(
        [
            TournamentMember(tournament_id=created.id, subject=OWNER.subject, role=Role.OWNER),
            TournamentMember(tournament_id=created.id, subject=ARBITER.subject, role=Role.ARBITER),
        ]
    )
    session.commit()
    return created
