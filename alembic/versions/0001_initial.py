"""Initial Central Ingest schema (dev-spec §6.2/§6.3/§6.4).

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22

This migration creates the full v0.1 schema. The append-only GRANT pattern for
the two audit tables is applied as a post-create SQL step — this is a no-op on
SQLite (test runs) and a REVOKE/GRANT on PostgreSQL (prod/staging).
"""

from __future__ import annotations

from alembic import op

from radivault_central.db.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        # FR-55/FR-57 append-only GRANTs. The central_app role is expected to
        # exist (``CREATE ROLE central_app NOINHERIT LOGIN`` by operator).
        op.execute("REVOKE ALL ON audit_ingest_event FROM PUBLIC;")
        op.execute("REVOKE ALL ON audit_anchor       FROM PUBLIC;")
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='central_app') THEN "
            "GRANT SELECT, INSERT ON audit_ingest_event TO central_app; "
            "GRANT SELECT, INSERT ON audit_anchor       TO central_app; "
            "END IF; END $$;"
        )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
