from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from seebach.platform.config import settings

CONNECT_TIMEOUT = 5

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings().database_url,
            pool_pre_ping=True,
            future=True,
            # A wrong host or port fails within seconds, not after the OS
            # gives up on a socket nobody answers.
            connect_args={"connect_timeout": CONNECT_TIMEOUT},
        )
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _factory


def get_session() -> Iterator[Session]:
    with session_factory()() as session:
        yield session
