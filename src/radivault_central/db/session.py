"""SQLAlchemy engine + session factory (sync, psycopg3).

A single process-wide engine is created lazily on first access and disposed at
shutdown by the FastAPI lifespan.
"""

from __future__ import annotations

from typing import TypeAlias

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

SessionFactory: TypeAlias = sessionmaker[Session]

_engine: Engine | None = None
_factory: SessionFactory | None = None


def get_engine(dsn: str, *, pool_size: int = 10, max_overflow: int = 10) -> Engine:
    """Return a process-wide :class:`Engine`, creating it on first call.

    SQLite uses a different pool class that doesn't accept size tuning kwargs,
    so we only pass them for non-sqlite DSNs.
    """
    global _engine, _factory
    if _engine is None:
        kwargs: dict = {"pool_pre_ping": True, "future": True}
        if not dsn.startswith("sqlite"):
            kwargs["pool_size"] = pool_size
            kwargs["max_overflow"] = max_overflow
        else:
            # allow multi-thread TestClient usage on in-memory sqlite
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(dsn, **kwargs)
        _factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory(dsn: str | None = None) -> SessionFactory:
    """Return the session factory. Call :func:`get_engine` first if needed."""
    if _factory is None:
        if dsn is None:
            raise RuntimeError("engine not initialised; pass dsn or call get_engine first")
        get_engine(dsn)
    assert _factory is not None
    return _factory


def reset_for_tests() -> None:
    """Dispose the engine/factory — unit-test helper only."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
