"""buyer-search-v3 — exact patient_age + study.kcd_* + hospital.region_pseudo.

Revision ID: 0007_v3_kcd_age_region
Revises: 0006_metadata_thumbnail_ingest
Create Date: 2026-04-25

dev-spec-buyer-search-v3 §6.1 / FR-V3-DATA-1, FR-V3-DATA-2, FR-V3-DATA-3.

Additive schema only:
- ``patient_pseudo.age``  INT NULL   (exact 0-120, deprecates age_bucket)
- ``study.kcd_code``      VARCHAR(10)
- ``study.kcd_label_ko``  VARCHAR(200)
- ``study.kcd_label_en``  VARCHAR(200)
- ``hospital.region_pseudo`` VARCHAR(20)

Plus 2 indexes (``idx_study_kcd_code``, ``idx_hospital_region_pseudo``) and
a seed UPDATE for the two demo hospitals (HOSP-001 → SEOUL-A,
HOSP-002 → BUSAN-B). The seed is wrapped in IF EXISTS clauses so the
migration is safe on a fresh DB without seed data.

CHECK constraints are Postgres-only (SQLite test runs ignore them — same
pattern as 0006).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_v3_kcd_age_region"
down_revision = "0006_metadata_thumbnail_ingest"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    """Lightweight introspection — works on SQLite + Postgres."""
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(table)}
    return column in cols


def _index_exists(bind, table: str, index: str) -> bool:
    insp = sa.inspect(bind)
    names = {ix["name"] for ix in insp.get_indexes(table)}
    return index in names


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 0001_initial uses ``Base.metadata.create_all()`` which means a fresh DB
    # already has the v3 ORM columns. We guard each ALTER with an existence
    # check so re-applying 0007 over either an upgraded 0006 schema OR a
    # fresh create_all is idempotent (FR-V3-OPS-1).

    # patient_pseudo.age — exact integer (0-120).
    if not _column_exists(bind, "patient_pseudo", "age"):
        op.add_column("patient_pseudo", sa.Column("age", sa.Integer(), nullable=True))
    if is_pg:
        op.execute(
            "ALTER TABLE patient_pseudo "
            "DROP CONSTRAINT IF EXISTS ck_patient_pseudo_age;"
        )
        op.execute(
            "ALTER TABLE patient_pseudo "
            "ADD CONSTRAINT ck_patient_pseudo_age "
            "CHECK (age IS NULL OR (age BETWEEN 0 AND 120));"
        )

    # study.kcd_*
    if not _column_exists(bind, "study", "kcd_code"):
        op.add_column("study", sa.Column("kcd_code", sa.String(length=10), nullable=True))
    if not _column_exists(bind, "study", "kcd_label_ko"):
        op.add_column("study", sa.Column("kcd_label_ko", sa.String(length=200), nullable=True))
    if not _column_exists(bind, "study", "kcd_label_en"):
        op.add_column("study", sa.Column("kcd_label_en", sa.String(length=200), nullable=True))
    if not _index_exists(bind, "study", "idx_study_kcd_code"):
        op.create_index("idx_study_kcd_code", "study", ["kcd_code"])

    # hospital.region_pseudo
    if not _column_exists(bind, "hospital", "region_pseudo"):
        op.add_column(
            "hospital", sa.Column("region_pseudo", sa.String(length=20), nullable=True)
        )
    if not _index_exists(bind, "hospital", "idx_hospital_region_pseudo"):
        op.create_index(
            "idx_hospital_region_pseudo", "hospital", ["region_pseudo"]
        )

    # Seed demo hospital region pseudos. Safe on empty DB — no-op then.
    op.execute(
        "UPDATE hospital SET region_pseudo = 'SEOUL-A' "
        "WHERE hospital_id = 'HOSP-001' AND region_pseudo IS NULL;"
    )
    op.execute(
        "UPDATE hospital SET region_pseudo = 'BUSAN-B' "
        "WHERE hospital_id = 'HOSP-002' AND region_pseudo IS NULL;"
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if _index_exists(bind, "hospital", "idx_hospital_region_pseudo"):
        op.drop_index("idx_hospital_region_pseudo", table_name="hospital")
    if _column_exists(bind, "hospital", "region_pseudo"):
        op.drop_column("hospital", "region_pseudo")

    if _index_exists(bind, "study", "idx_study_kcd_code"):
        op.drop_index("idx_study_kcd_code", table_name="study")
    if _column_exists(bind, "study", "kcd_label_en"):
        op.drop_column("study", "kcd_label_en")
    if _column_exists(bind, "study", "kcd_label_ko"):
        op.drop_column("study", "kcd_label_ko")
    if _column_exists(bind, "study", "kcd_code"):
        op.drop_column("study", "kcd_code")

    if is_pg:
        op.execute("ALTER TABLE patient_pseudo DROP CONSTRAINT IF EXISTS ck_patient_pseudo_age;")
    if _column_exists(bind, "patient_pseudo", "age"):
        op.drop_column("patient_pseudo", "age")
