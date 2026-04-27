"""Structural tests for alembic revision ``0009_text_search_description_phase15``.

Validates on the SQLite test target (the Postgres tsvector / GIN steps are
short-circuited per the migration's `is_pg` gate):
- upgrade adds ``study.study_description``, ``study.protocol_name``,
  ``series.series_description``.
- upgrade creates ``study_phi_quarantine_audit`` table with the expected
  columns (audit_pk, study_pk, scrub_version, blacklist_matched, ...).
- upgrade is idempotent (second call is no-op).
- downgrade removes the new columns + table cleanly.
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
    chain = []
    for fname in sorted(versions.glob("*.py")):
        if fname.stem.startswith("000"):
            chain.append(_load(f"mig_{fname.stem}", fname))
    return chain


def _apply_chain_upgrade(chain, conn) -> None:
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        for mod in chain:
            mod.upgrade()
    conn.commit()


def test_upgrade_adds_description_columns_and_quarantine_table(migrations) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        _apply_chain_upgrade(migrations, conn)

    insp = inspect(engine)
    study_cols = {c["name"] for c in insp.get_columns("study")}
    series_cols = {c["name"] for c in insp.get_columns("series")}
    tables = set(insp.get_table_names())

    assert "study_description" in study_cols
    assert "protocol_name" in study_cols
    assert "series_description" in series_cols
    assert "study_phi_quarantine_audit" in tables

    audit_cols = {c["name"] for c in insp.get_columns("study_phi_quarantine_audit")}
    expected = {
        "audit_pk",
        "study_pk",
        "quarantined_at",
        "scrub_version",
        "blacklist_matched",
        "whitelist_matched",
        "suspicious_token_count",
        "before_hash",
        "after_hash",
        "reviewed_by",
        "reviewed_at",
        "review_decision",
    }
    assert expected <= audit_cols

    engine.dispose()


def test_upgrade_is_idempotent(migrations) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        _apply_chain_upgrade(migrations, conn)
        # Re-run only the 0009 step — must be a no-op.
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migrations[-1].upgrade()
        conn.commit()
    engine.dispose()


def test_downgrade_removes_description_columns_and_quarantine_table(
    migrations,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        _apply_chain_upgrade(migrations, conn)
        # Downgrade only the last revision.
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migrations[-1].downgrade()
        conn.commit()

    insp = inspect(engine)
    study_cols = {c["name"] for c in insp.get_columns("study")}
    series_cols = {c["name"] for c in insp.get_columns("series")}
    tables = set(insp.get_table_names())

    assert "study_description" not in study_cols
    assert "protocol_name" not in study_cols
    assert "series_description" not in series_cols
    assert "study_phi_quarantine_audit" not in tables

    engine.dispose()


def test_postgres_tsvector_re_definition_present_in_source() -> None:
    """The Postgres path is exercised live in the demo verification stage;
    here we only assert the migration source still contains the new
    weight allocation (A=description/protocol, B=KCD/body, C=modality,
    D=mfr/model) so a future refactor cannot silently regress it."""
    root = pathlib.Path(__file__).resolve().parents[3]
    text = (
        root / "alembic" / "versions" / "0009_text_search_description_phase15.py"
    ).read_text()
    # Weight A — study_description / protocol_name.
    assert "coalesce(study_description, '')), 'A'" in text
    assert "coalesce(protocol_name, '')), 'A'" in text
    # Weight B — body_part / kcd_label_en.
    assert "coalesce(body_part, '')), 'B'" in text
    assert "coalesce(kcd_label_en, '')), 'B'" in text
    # Weight C — kcd_label_ko / modality.
    assert "coalesce(kcd_label_ko, '')), 'C'" in text
    assert "coalesce(modality, '')), 'C'" in text
    # CONCURRENTLY usage for production safety.
    assert "CREATE INDEX CONCURRENTLY" in text
