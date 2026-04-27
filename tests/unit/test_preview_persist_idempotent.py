"""Idempotency tests for ``PgFrameWriter.write_frame_rows`` (FR-PREVIEW-12).

Background
----------
After the multi-PACS HOSP-002 stamping fix (commit ``88cbd43``) the
gateway sync-once retry path showed ``preview_status='pending'`` for
10 series. Audit log root cause:

    preview.failed: (psycopg.errors.UniqueViolation)
    duplicate key value violates unique constraint "uq_dpf_series_frame"

Flow:
  1. First sync-once → ``_persist_preview_batch`` inserted N
     ``dicom_preview_frame`` rows → manifest-stamping 403 →
     central upload aborted.
  2. Retry (after stamping fix) → same series re-runs →
     ``write_frame_rows`` re-attempts the same
     ``(pseudo_series_uid, frame_idx)`` pairs → UniqueViolation →
     ``preview.failed`` → series stays ``pending``.

Fix
---
``write_frame_rows`` now emits a dialect-specific
``INSERT ... ON CONFLICT (pseudo_series_uid, frame_idx) DO NOTHING``
so retries silently absorb duplicate frames. The frame set is
deterministic per series (driven by instance count) so swallowing
duplicates loses no data.

Notes
-----
* SQLite (>=3.24) supports the same ``ON CONFLICT`` clause as Postgres
  via ``sqlalchemy.dialects.sqlite.insert``. We exercise that path here
  as a reasonable proxy for the production PG behaviour — the SQL
  statement we emit is structurally identical.
* ``phi_scrub_audit`` has no unique constraint (only indexes) so it is
  intentionally append-only and needs no idempotency change. Test
  ``test_phi_scrub_audit_has_no_unique_constraint`` pins that
  invariant so a future schema change can't silently break this
  assumption.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from radivault_central.db.models import (
    Base,
    DicomPreviewFrame,
    PhiScrubAudit,
)
from radivault_gateway.preview_clients import PgFrameWriter
from radivault_gateway.preview_pipeline import FrameRecord


@pytest.fixture
def writer_with_session():
    """Fresh sqlite engine + sessionmaker + PgFrameWriter per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    writer = PgFrameWriter(session_factory=sf)
    yield writer, sf
    engine.dispose()


def _frame(idx: int, *, series_uid: str = "RV-SER-A") -> FrameRecord:
    return FrameRecord(
        frame_idx=idx,
        minio_key=f"previews/RV-STD-A/{series_uid}/{idx:04d}.jpg",
        width=512,
        height=512,
        byte_size=12_345,
        sha256="a" * 64,
        phi_scrub_method="afni_refacer_v0_7",
        source_instance_uid_pseudo=None,
    )


# ---------------------------------------------------------------------------
# Case 1 — duplicate (pseudo_series_uid, frame_idx) is silent (no raise)
# ---------------------------------------------------------------------------


def test_duplicate_series_frame_idx_is_silent(writer_with_session):
    """Two attempts at the same (series, frame_idx) → second is no-op."""
    writer, sf = writer_with_session
    frames = [_frame(0), _frame(1), _frame(2)]

    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-A",
        frames=frames,
    )

    # Second call with the SAME frames must not raise UniqueViolation /
    # IntegrityError. Pre-fix this raised psycopg.errors.UniqueViolation
    # on the (pseudo_series_uid, frame_idx) constraint.
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-A",
        frames=frames,
    )

    with sf() as session:
        rows = session.execute(select(DicomPreviewFrame)).scalars().all()
        # Exactly the original 3 — no duplicates were inserted.
        assert len(rows) == 3
        assert {r.frame_idx for r in rows} == {0, 1, 2}


# ---------------------------------------------------------------------------
# Case 2 — different frame_idx (same series) all land
# ---------------------------------------------------------------------------


def test_different_frame_idx_all_persist(writer_with_session):
    """Distinct frame_idx values within the same series all insert."""
    writer, sf = writer_with_session

    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-A",
        frames=[_frame(0), _frame(1)],
    )
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-A",
        frames=[_frame(2), _frame(3), _frame(4)],
    )

    with sf() as session:
        rows = session.execute(select(DicomPreviewFrame)).scalars().all()
        assert {r.frame_idx for r in rows} == {0, 1, 2, 3, 4}


# ---------------------------------------------------------------------------
# Case 3 — same frame_idx but different pseudo_series_uid all land
# ---------------------------------------------------------------------------


def test_different_series_uid_all_persist(writer_with_session):
    """Same frame_idx across different series must coexist."""
    writer, sf = writer_with_session

    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-A",
        frames=[_frame(0, series_uid="RV-SER-A")],
    )
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-B",
        frames=[_frame(0, series_uid="RV-SER-B")],
    )
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-C",
        frames=[_frame(0, series_uid="RV-SER-C")],
    )

    with sf() as session:
        rows = session.execute(select(DicomPreviewFrame)).scalars().all()
        # 3 rows, all frame_idx=0 but different series.
        assert len(rows) == 3
        assert {r.pseudo_series_uid for r in rows} == {
            "RV-SER-A",
            "RV-SER-B",
            "RV-SER-C",
        }
        assert {r.frame_idx for r in rows} == {0}


# ---------------------------------------------------------------------------
# Case 4 — partial first run + retry → exactly-once final state
# ---------------------------------------------------------------------------


def test_partial_run_then_retry_lands_full_set(writer_with_session):
    """Simulates the HOSP-002 retry scenario:

    Run 1 persists frames 0..2 then central upload fails (here we just
    stop). Run 2 retries the *full* deterministic frame set 0..4. The
    final state must contain each frame exactly once — frames 0..2 are
    de-duped (silent), frames 3..4 are inserted fresh.
    """
    writer, sf = writer_with_session

    # Run 1 — partial (frames 0..2 persist, then "central upload" fails).
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-A",
        frames=[_frame(0), _frame(1), _frame(2)],
    )

    with sf() as session:
        rows = session.execute(select(DicomPreviewFrame)).scalars().all()
        assert len(rows) == 3, "run-1 should persist all 3 frames"

    # Run 2 — full frame set retried (deterministic from instance count).
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-A",
        pseudo_series_uid="RV-SER-A",
        frames=[_frame(i) for i in range(5)],
    )

    with sf() as session:
        rows = session.execute(select(DicomPreviewFrame)).scalars().all()
        # Exactly 5 rows — 0..2 carried over, 3..4 newly inserted.
        assert len(rows) == 5
        assert {r.frame_idx for r in rows} == {0, 1, 2, 3, 4}
        # No duplicates per (series, idx).
        keys = [(r.pseudo_series_uid, r.frame_idx) for r in rows]
        assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# phi_scrub_audit invariant — append-only, no unique constraint
# ---------------------------------------------------------------------------


def test_phi_scrub_audit_has_no_unique_constraint():
    """Pin: ``phi_scrub_audit`` is intentionally append-only — there
    is no unique constraint, only indexes. Multiple retry attempts for
    the same series MAY produce multiple audit rows; that is correct
    audit-log behaviour (one row per pipeline invocation, even
    failures). If a future schema change introduces a unique constraint
    we must mirror the FR-PREVIEW-12 idempotency fix to
    ``PgAuditWriter`` — this test fails fast in that case so the gap
    can't go unnoticed.
    """
    table = PhiScrubAudit.__table__
    unique_constraints = [
        c for c in table.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert unique_constraints == [], (
        "phi_scrub_audit gained a UniqueConstraint — mirror the "
        "FR-PREVIEW-12 ON CONFLICT DO NOTHING fix into PgAuditWriter "
        "or this retry path will regress."
    )
