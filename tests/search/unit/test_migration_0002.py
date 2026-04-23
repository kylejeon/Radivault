"""Structural tests for alembic revision ``0002_metadata_index``.

Validates:
- upgrade is idempotent (re-running does not raise)
- downgrade cleanly removes the three new tables + composite indexes
- SQLite test target skips the PG-only role GRANT branch
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def migrations():
    root = pathlib.Path(__file__).resolve().parents[3]
    versions = root / "alembic" / "versions"
    m1 = _load("mig_0001_initial", versions / "0001_initial.py")
    m2 = _load("mig_0002_metadata_index", versions / "0002_metadata_index.py")
    return m1, m2


def test_upgrade_creates_expected_objects(migrations) -> None:
    m1, m2 = migrations
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            m1.upgrade()
            m2.upgrade()
        conn.commit()

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {"buyer", "buyer_api_key", "search_audit"} <= tables
    study_ix = {ix["name"] for ix in insp.get_indexes("study")}
    assert {
        "idx_study_date_keyset",
        "idx_study_filter_keyset",
        "idx_study_ingested_keyset",
    } <= study_ix
    engine.dispose()


def test_upgrade_is_idempotent(migrations) -> None:
    """Second invocation must not raise — enables safe re-runs on operator retry."""
    m1, m2 = migrations
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            m1.upgrade()
            m2.upgrade()
            m2.upgrade()  # second time — must be a no-op
        conn.commit()
    engine.dispose()


def test_search_audit_pk_contains_created_at_on_pg_shape() -> None:
    """H-5 — on PostgreSQL the migration promotes the PK to
    ``(audit_pk, created_at)`` to make the table partitionable by range.

    SQLite cannot express ``AUTOINCREMENT`` on a composite PK, so the ORM
    declares a single-column PK; the migration does the PG-specific
    ALTER. Here we verify the migration module contains that ALTER so the
    PG path is at least statically present. (A live-PG integration test
    is planned for v0.1.1 QA when a PG fixture is wired.)
    """
    root = pathlib.Path(__file__).resolve().parents[3]
    text = (root / "alembic" / "versions" / "0002_metadata_index.py").read_text()
    assert "PRIMARY KEY (audit_pk, created_at)" in text
    # And the downgrade restores the single-column PK.
    assert "PRIMARY KEY (audit_pk)" in text


def test_downgrade_removes_new_objects(migrations) -> None:
    m1, m2 = migrations
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            m1.upgrade()
            m2.upgrade()
            m2.downgrade()
        conn.commit()

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "buyer" not in tables
    assert "buyer_api_key" not in tables
    assert "search_audit" not in tables
    study_ix = {ix["name"] for ix in insp.get_indexes("study")}
    assert "idx_study_date_keyset" not in study_ix
    assert "idx_study_filter_keyset" not in study_ix
    assert "idx_study_ingested_keyset" not in study_ix
    engine.dispose()
