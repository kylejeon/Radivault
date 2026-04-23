"""De-ID pixel (v0.2) — pixel_audit_event + study_job.state enum extension.

Revision ID: 0003_de_id_pixel
Revises: 0002_metadata_index
Create Date: 2026-04-22

Scope notes
-----------
The gateway-local ``study_job`` and the new ``pixel_audit_event`` table live
inside the gateway's SQLite state DB (``configs/gateway.*.yaml``'s
``state.db_path``). The gateway creates/migrates that schema at runtime via
:mod:`radivault_gateway.state.db` using idempotent ``CREATE TABLE IF NOT
EXISTS`` (dev-spec-de-id-pixel §6.2 explicitly rejects an Alembic migration
for the gateway state DB).

This Alembic revision is therefore **guarded**: on PostgreSQL it is a no-op
plus an optional GRANT for the future central-side pixel audit viewer role;
on SQLite it is a no-op. We keep the revision to document the schema bump
and give any future Alembic-managed environment a reversible anchor point.
"""

from __future__ import annotations

from alembic import op

revision = "0003_de_id_pixel"
down_revision = "0002_metadata_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # FR-32 (dev-spec-de-id-pixel): ``study_job.state`` gains the three
        # pixel-specific values. The gateway enforces states in Python so no
        # DB-side enum alteration is required. We emit a guarded comment so
        # operators browsing the schema know the new values exist. If a
        # future iteration promotes pixel_audit_event into a central-visible
        # table this is the ALTER site.
        op.execute(
            "COMMENT ON COLUMN study_job.state IS 'v0.2 adds pixel_processing | "
            "pixel_deided | pixel_failed (gateway-enforced enum; see "
            "radivault_gateway.state.StudyState).'"
        )
    # SQLite: no-op. Gateway runtime creates pixel_audit_event via
    # radivault_gateway.state.db.SCHEMA.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("COMMENT ON COLUMN study_job.state IS NULL")
