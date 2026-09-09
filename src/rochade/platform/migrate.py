"""Run the packaged migrations from code.

The migration scripts ship inside the package, so the API can bring a
database up to date on startup without an alembic.ini beside it. The same
configuration serves the test suite, which is how a handler test is also a
test that the migrations produce the schema the code expects.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS = Path(__file__).parent / "migrations"

log = logging.getLogger(__name__)


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_to_head(database_url: str) -> None:
    log.info("applying migrations")
    command.upgrade(alembic_config(database_url), "head")
