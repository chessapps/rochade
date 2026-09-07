from alembic import context
from sqlalchemy import engine_from_config, pool

from seebach.platform.config import settings
from seebach.platform.db import CONNECT_TIMEOUT
from seebach.shared.models import Base

config = context.config
# Only fall back to the configured database. A caller that already supplied a
# URL -- the test suite pointing at a throwaway container, for instance -- must
# win, or every migration silently runs somewhere else.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": CONNECT_TIMEOUT},
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
