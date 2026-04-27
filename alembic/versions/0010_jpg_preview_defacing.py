"""jpg-preview-defacing — preview pipeline schema deltas.

Revision ID: 0010_jpg_preview_defacing
Revises: 0009_text_search_phase15
Create Date: 2026-04-27

dev-spec-jpg-preview-defacing §6 (FR-PREVIEW-12 / FR-PREVIEW-13 / FR-AUDIT-1).

Three deltas in one revision (per Kyle's "fewer revisions" preference):

1. ALTER ``series`` — add 6 preview-pipeline columns
   (the dev-spec calls the table ``dicom_series``; the actual ORM table
   name is ``series``). Names mirror dev-spec §6.1 exactly.
2. CREATE ``dicom_preview_frame`` — per-frame metadata + MinIO key + sha256.
3. CREATE ``phi_scrub_audit`` — series-level audit row of every defacing
   pipeline invocation.

NEW INGESTIONS ONLY (FR-NEWONLY-1/2): existing ``series`` rows keep the
column DEFAULT 'pending'; we do **not** issue any UPDATE / backfill.
Buyer BFF treats ``preview_status != 'generated'`` as 404, so legacy
rows automatically render the existing fallback path (silent
coexistence — FR-NEWONLY-3).

Dialect notes
-------------
- Postgres path: real CHECK constraints + indexes.
- SQLite path (test runs): same columns / same tables, but CHECK
  constraints are accepted by SQLite and validated. ``timestamptz`` maps
  to ``DATETIME``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_jpg_preview_defacing"
down_revision = "0009_text_search_phase15"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def _table_exists(bind, table: str) -> bool:
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def _index_exists(bind, table: str, index: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return index in {ix["name"] for ix in insp.get_indexes(table)}


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. ALTER series — 6 new columns (FR-PREVIEW-12). All NULL or have
    #    safe DEFAULTs so existing rows keep working without backfill
    #    (FR-NEWONLY-2).
    if not _column_exists(bind, "series", "preview_status"):
        op.add_column(
            "series",
            sa.Column(
                "preview_status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            ),
        )
        if is_pg:
            op.execute(
                "ALTER TABLE series ADD CONSTRAINT ck_series_preview_status "
                "CHECK (preview_status IN ('generated','skipped','quarantined','pending'));"
            )

    if not _column_exists(bind, "series", "preview_frame_count"):
        op.add_column(
            "series",
            sa.Column(
                "preview_frame_count",
                sa.Integer,
                nullable=False,
                server_default="0",
            ),
        )

    if not _column_exists(bind, "series", "preview_deface_decision"):
        op.add_column(
            "series",
            sa.Column(
                "preview_deface_decision",
                sa.String(length=40),
                nullable=True,
            ),
        )
        if is_pg:
            op.execute(
                "ALTER TABLE series ADD CONSTRAINT ck_series_preview_deface_decision "
                "CHECK (preview_deface_decision IS NULL OR preview_deface_decision IN "
                "('required','not_required','skipped_unsupported_modality'));"
            )

    if not _column_exists(bind, "series", "preview_deface_method"):
        op.add_column(
            "series",
            sa.Column(
                "preview_deface_method",
                sa.String(length=40),
                nullable=True,
            ),
        )

    if not _column_exists(bind, "series", "preview_generated_at"):
        op.add_column(
            "series",
            sa.Column(
                "preview_generated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    if not _column_exists(bind, "series", "preview_pipeline_version"):
        op.add_column(
            "series",
            sa.Column(
                "preview_pipeline_version",
                sa.String(length=32),
                nullable=False,
                server_default="0.1.0",
            ),
        )

    if not _index_exists(bind, "series", "ix_series_preview_status"):
        op.create_index(
            "ix_series_preview_status",
            "series",
            ["preview_status"],
        )

    # 2. CREATE dicom_preview_frame (FR-PREVIEW-13).
    if not _table_exists(bind, "dicom_preview_frame"):
        op.create_table(
            "dicom_preview_frame",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("pseudo_series_uid", sa.String(length=64), nullable=False),
            sa.Column("pseudo_study_uid", sa.String(length=64), nullable=False),
            sa.Column("frame_idx", sa.Integer, nullable=False),
            sa.Column("minio_key", sa.String(length=255), nullable=False),
            sa.Column("width", sa.Integer, nullable=False),
            sa.Column("height", sa.Integer, nullable=False),
            sa.Column("byte_size", sa.Integer, nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("phi_scrub_method", sa.String(length=40), nullable=False),
            sa.Column(
                "source_instance_uid_pseudo",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "pseudo_series_uid",
                "frame_idx",
                name="uq_dpf_series_frame",
            ),
        )
        op.create_index(
            "ix_dpf_study",
            "dicom_preview_frame",
            ["pseudo_study_uid"],
        )

    # 3. CREATE phi_scrub_audit (FR-AUDIT-1).
    if not _table_exists(bind, "phi_scrub_audit"):
        op.create_table(
            "phi_scrub_audit",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("pseudo_study_uid", sa.String(length=64), nullable=False),
            sa.Column("pseudo_series_uid", sa.String(length=64), nullable=False),
            sa.Column("modality", sa.String(length=8), nullable=False),
            sa.Column("body_part", sa.String(length=32), nullable=True),
            sa.Column("deface_decision", sa.String(length=40), nullable=False),
            sa.Column(
                "deface_decision_reason",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column("phi_scrub_method", sa.String(length=40), nullable=False),
            sa.Column(
                "sidecar_image_tag",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column("afni_version", sa.String(length=32), nullable=True),
            sa.Column("duration_ms", sa.Integer, nullable=True),
            sa.Column(
                "outcome",
                sa.String(length=20),
                nullable=False,
            ),
            sa.Column("error_code", sa.String(length=40), nullable=True),
            sa.Column("error_detail", sa.String(length=2000), nullable=True),
            sa.Column(
                "pipeline_version",
                sa.String(length=32),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        if is_pg:
            op.execute(
                "ALTER TABLE phi_scrub_audit ADD CONSTRAINT ck_psa_outcome "
                "CHECK (outcome IN "
                "('success','quarantine_input','quarantine_runtime',"
                "'skipped','not_required'));"
            )
        op.create_index("ix_psa_study", "phi_scrub_audit", ["pseudo_study_uid"])
        op.create_index(
            "ix_psa_series", "phi_scrub_audit", ["pseudo_series_uid"]
        )
        op.create_index("ix_psa_outcome", "phi_scrub_audit", ["outcome"])


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 3. Drop phi_scrub_audit.
    if _table_exists(bind, "phi_scrub_audit"):
        if is_pg:
            op.execute("DROP INDEX IF EXISTS ix_psa_outcome;")
            op.execute("DROP INDEX IF EXISTS ix_psa_series;")
            op.execute("DROP INDEX IF EXISTS ix_psa_study;")
        op.drop_table("phi_scrub_audit")

    # 2. Drop dicom_preview_frame.
    if _table_exists(bind, "dicom_preview_frame"):
        if is_pg:
            op.execute("DROP INDEX IF EXISTS ix_dpf_study;")
        op.drop_table("dicom_preview_frame")

    # 1. Drop series preview columns.
    if _index_exists(bind, "series", "ix_series_preview_status"):
        op.drop_index("ix_series_preview_status", table_name="series")
    if is_pg:
        op.execute(
            "ALTER TABLE series DROP CONSTRAINT IF EXISTS "
            "ck_series_preview_deface_decision;"
        )
        op.execute(
            "ALTER TABLE series DROP CONSTRAINT IF EXISTS "
            "ck_series_preview_status;"
        )
    for col in (
        "preview_pipeline_version",
        "preview_generated_at",
        "preview_deface_method",
        "preview_deface_decision",
        "preview_frame_count",
        "preview_status",
    ):
        if _column_exists(bind, "series", col):
            op.drop_column("series", col)
