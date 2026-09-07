"""The API brings its database up to date when it starts."""

from __future__ import annotations

import pytest
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from seebach.app import create_app
from seebach.platform.config import settings
from seebach.platform.migrate import MIGRATIONS, alembic_config


def test_the_packaged_migrations_are_the_ones_that_run() -> None:
    config = alembic_config("postgresql+psycopg://x@localhost/x")
    assert config.get_main_option("script_location") == str(MIGRATIONS)
    assert ScriptDirectory.from_config(config).get_current_head() is not None


def test_startup_leaves_the_database_at_head(
    engine: Engine, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEEBACH_DATABASE_URL", database_url)
    monkeypatch.setenv("SEEBACH_MIGRATE_ON_START", "true")
    settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200
    finally:
        settings.cache_clear()

    head = ScriptDirectory.from_config(alembic_config(database_url)).get_current_head()
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version"))
        versions = rows.scalars().all()
    assert versions == [head]
