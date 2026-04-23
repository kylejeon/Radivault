"""Read-only engine + session factory for radivault_search.

Mirrors the central-ingest pattern but scoped to the buyer_ro role.
"""

from __future__ import annotations

from typing import TypeAlias

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

SessionFactory: TypeAlias = sessionmaker[Session]

_engine: Engine | None = None
_factory: SessionFactory | None = None


def get_engine(dsn: str, *, pool_size: int = 30, max_overflow: int = 20) -> Engine:
    """Return a process-wide read-only :class:`Engine`, creating it on first call."""
    global _engine, _factory
    if _engine is None:
        kwargs: dict = {"pool_pre_ping": True, "future": True}
        if not dsn.startswith("sqlite"):
            kwargs["pool_size"] = pool_size
            kwargs["max_overflow"] = max_overflow
        else:
            # ``:memory:`` SQLite requires a StaticPool so every connection
            # shares the same in-memory DB — otherwise each checkout opens
            # a fresh (empty) database and tests see ``no such table``.
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
        _engine = create_engine(dsn, **kwargs)
        _factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory(dsn: str | None = None) -> SessionFactory:
    if _factory is None:
        if dsn is None:
            raise RuntimeError("engine not initialised; pass dsn or call get_engine first")
        get_engine(dsn)
    assert _factory is not None
    return _factory


def reset_for_tests() -> None:
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
