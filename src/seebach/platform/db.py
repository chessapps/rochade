from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from seebach.platform.config import settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings().database_url, pool_pre_ping=True, future=True)
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _factory


def get_session() -> Iterator[Session]:
    with session_factory()() as session:
        yield session
