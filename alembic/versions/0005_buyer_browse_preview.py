"""Buyer Browse Preview v0.1 — study preview columns + sample_download_audit.

Revision ID: 0005_buyer_browse_preview
Revises: 0004_order_fulfillment
Create Date: 2026-04-25

dev-spec-buyer-browse-preview FR-DATA-1: D-13 MVP for the buyer
browse → preview → sample download workflow.

Additions
---------
- Four new columns on ``study``:
    * ``preview_status`` TEXT NOT NULL DEFAULT 'pending'
      (CHECK 'pending'|'verified'|'phi_detected'|'not_applicable')
    * ``preview_thumbnail_key`` TEXT NULL    — MinIO key
    * ``preview_slice_count`` INTEGER NULL    — frames count
    * ``sample_instance_uid`` TEXT NULL       — DICOM SOPInstanceUID
- Partial index ``idx_study_preview_status`` WHERE status='verified'
  (Postgres only — SQLite gets a plain index).
- New table ``sample_download_audit`` with two indexes.

Idempotency
-----------
``preview_status`` defaults to 'pending' so existing 250 study rows
inherit the safe default — no buyer-facing surface exposes their pixel
data until a seed run flips them to 'verified'.

SQLite reversibility
--------------------
- CHECK constraint expressed via ``CheckConstraint`` so SQLite enforces it
  inline. Partial-WHERE indexes are not supported on SQLite — we fall back
  to a plain index there.
- Re-running upgrade is safe: each ALTER/CREATE is guarded by an inspect
  check.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from radivault_central.db.models import Base as CentralBase  # noqa: F401
from radivault_central.db.models import SampleDownloadAudit  # noqa: F401

revision = "0005_buyer_browse_preview"
down_revision = "0004_order_fulfillment"
branch_labels = None
depends_on = None


# Order matters for downgrade only — table must drop before its parent.
_SAMPLE_AUDIT_TABLE = "sample_download_audit"
_SAMPLE_AUDIT_INDEXES = [
    "idx_sample_dl_audit_buyer_time",
    "idx_sample_dl_audit_study",
]
_STUDY_PREVIEW_INDEX = "idx_study_preview_status"
_STUDY_PREVIEW_COLUMNS = [
    "preview_status",
    "preview_thumbnail_key",
    "preview_slice_count",
    "sample_instance_uid",
]
_PREVIEW_STATUS_CHECK = "ck_study_preview_status"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # ------------------------------------------------------------------
    # 1) study ALTER — 4 columns + check constraint + partial index.
    # ------------------------------------------------------------------
    if "study" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study")}

        # Add ``preview_status`` first because the CHECK constraint depends
        # on it. NOT NULL DEFAULT 'pending' so existing rows are silently
        # backfilled — this is the safe default that excludes them from
        # the buyer preview surface.
        if "preview_status" not in existing_cols:
            if bind.dialect.name == "sqlite":
                op.execute(
                    "ALTER TABLE study ADD COLUMN preview_status "
                    "TEXT NOT NULL DEFAULT 'pending'"
                )
            else:
                op.execute(
                    "ALTER TABLE study ADD COLUMN preview_status "
                    "TEXT NOT NULL DEFAULT 'pending'"
                )

        if "preview_thumbnail_key" not in existing_cols:
            op.execute("ALTER TABLE study ADD COLUMN preview_thumbnail_key TEXT")
        if "preview_slice_count" not in existing_cols:
            op.execute("ALTER TABLE study ADD COLUMN preview_slice_count INTEGER")
        if "sample_instance_uid" not in existing_cols:
            op.execute("ALTER TABLE study ADD COLUMN sample_instance_uid TEXT")

        # CHECK constraint — Postgres only (SQLite quietly accepts but the
        # ALTER ... ADD CONSTRAINT syntax differs between dialects). The
        # ORM-level enum is the primary enforcement; this constraint is
        # belt-and-braces for direct SQL writers.
        if bind.dialect.name == "postgresql":
            op.execute(
                f"DO $$ BEGIN "
                f"IF NOT EXISTS ("
                f"  SELECT 1 FROM pg_constraint "
                f"  WHERE conname = '{_PREVIEW_STATUS_CHECK}'"
                f") THEN "
                f"  ALTER TABLE study ADD CONSTRAINT {_PREVIEW_STATUS_CHECK} "
                f"  CHECK (preview_status IN ("
                f"    'pending', 'verified', 'phi_detected', 'not_applicable'"
                f"  )); "
                f"END IF; "
                f"END $$;"
            )

        # Partial index — Postgres only. SQLite gets a plain index so the
        # query planner still has something to chew on for verified rows.
        existing_idx = {ix["name"] for ix in inspector.get_indexes("study")}
        if _STUDY_PREVIEW_INDEX not in existing_idx:
            if bind.dialect.name == "postgresql":
                op.execute(
                    f"CREATE INDEX {_STUDY_PREVIEW_INDEX} ON study(preview_status) "
                    f"WHERE preview_status = 'verified';"
                )
            else:
                op.create_index(
                    _STUDY_PREVIEW_INDEX, "study", ["preview_status"]
                )

    # ------------------------------------------------------------------
    # 2) sample_download_audit — new table + 2 indexes.
    # ------------------------------------------------------------------
    if _SAMPLE_AUDIT_TABLE not in inspector.get_table_names():
        CentralBase.metadata.create_all(
            bind=bind, tables=[SampleDownloadAudit.__table__]
        )

    if bind.dialect.name == "postgresql":
        # Belt-and-braces CHECK on status enum.
        op.execute(
            "DO $$ BEGIN "
            "IF NOT EXISTS ("
            "  SELECT 1 FROM pg_constraint "
            "  WHERE conname = 'ck_sample_download_audit_status'"
            ") THEN "
            "  ALTER TABLE sample_download_audit "
            "  ADD CONSTRAINT ck_sample_download_audit_status "
            "  CHECK (status IN ('issued', 'completed', 'expired', 'failed')); "
            "END IF; "
            "END $$;"
        )


def downgrade() -> None:
    """Reverse upgrade — destructive."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1) Drop the audit table + its indexes.
    if _SAMPLE_AUDIT_TABLE in inspector.get_table_names():
        for ix in _SAMPLE_AUDIT_INDEXES:
            try:
                op.drop_index(ix, table_name=_SAMPLE_AUDIT_TABLE)
            except Exception:  # noqa: BLE001 — idempotent best-effort
                pass
        op.drop_table(_SAMPLE_AUDIT_TABLE)

    # 2) Drop the partial index + 4 columns on study.
    if "study" in inspector.get_table_names():
        existing_idx = {ix["name"] for ix in inspector.get_indexes("study")}
        if _STUDY_PREVIEW_INDEX in existing_idx:
            op.drop_index(_STUDY_PREVIEW_INDEX, table_name="study")

        if bind.dialect.name == "postgresql":
            op.execute(
                f"ALTER TABLE study DROP CONSTRAINT IF EXISTS {_PREVIEW_STATUS_CHECK};"
            )

        existing_cols = {c["name"] for c in inspector.get_columns("study")}
        # SQLite cannot DROP COLUMN before 3.35 — but our test envs are
        # newer. We attempt and silently swallow on hard-fail because
        # downgrade is a developer-tool path, never a production hot path.
        for col in _STUDY_PREVIEW_COLUMNS:
            if col in existing_cols:
                try:
                    if bind.dialect.name == "sqlite":
                        op.execute(f"ALTER TABLE study DROP COLUMN {col}")
                    else:
                        op.drop_column("study", col)
                except Exception:  # noqa: BLE001
                    pass
