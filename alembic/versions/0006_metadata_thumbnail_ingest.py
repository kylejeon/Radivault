"""metadata-thumbnail-ingest v2 — preview_status enum 'auto_verified'.

Revision ID: 0006_metadata_thumbnail_ingest
Revises: 0005_buyer_browse_preview
Create Date: 2026-04-25

dev-spec-metadata-thumbnail-ingest §6.2 / FR-INGEST-1.3:
- ``study.preview_status`` was originally CHECK-constrained to
  ('pending', 'verified', 'phi_detected', 'not_applicable'). The new ingest
  flow sets ``auto_verified`` when the Gateway-generated thumbnail passed the
  BurnedInAnnotation gate without operator review. Add it to the CHECK list.

Idempotent — re-running is a no-op.
"""

from __future__ import annotations

from alembic import op

revision = "0006_metadata_thumbnail_ingest"
down_revision = "0005_buyer_browse_preview"
branch_labels = None
depends_on = None

NEW_CHECK_VALUES = (
    "'pending', 'auto_verified', 'verified', 'phi_detected', 'not_applicable'"
)
OLD_CHECK_VALUES = (
    "'pending', 'verified', 'phi_detected', 'not_applicable'"
)
CONSTRAINT = "ck_study_preview_status"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite test runs use the ORM string column directly; the CHECK
        # constraint is Postgres-specific (declared in 0005).
        return
    op.execute(f"ALTER TABLE study DROP CONSTRAINT IF EXISTS {CONSTRAINT};")
    op.execute(
        f"ALTER TABLE study ADD CONSTRAINT {CONSTRAINT} "
        f"CHECK (preview_status IN ({NEW_CHECK_VALUES}));"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Restore the original 4-value CHECK. Any rows in 'auto_verified' will
    # need to be migrated first; we leave that to the operator.
    op.execute(f"ALTER TABLE study DROP CONSTRAINT IF EXISTS {CONSTRAINT};")
    op.execute(
        f"ALTER TABLE study ADD CONSTRAINT {CONSTRAINT} "
        f"CHECK (preview_status IN ({OLD_CHECK_VALUES}));"
    )
