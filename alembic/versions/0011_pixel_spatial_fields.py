"""pixel/spatial fields — Tier-1 Series columns.

Revision ID: 0011_pixel_spatial_fields
Revises: 0010_jpg_preview_defacing
Create Date: 2026-04-29

dev-spec-pixel-spatial-fields §6.5 FR-PSF-4.7 / FR-PSF-4.3.

Adds 9 Tier-1 series-level columns + reuses the manifest values for the
2 already-extracted fields (kvp, slice_thickness_mm — FR-PSF-2 had them
but the central ingest path never persisted them to dedicated columns).

All columns are nullable so legacy rows ingested under v1/v2 manifests
(or pre-Phase-1.5 wipe) keep working without backfill (FR-PSF-3.5 /
FR-PSF-9 — Postgres wipe + re-sync is the documented backfill path,
not ALTER UPDATE).

Column-name notes (Q-PSF-7 default):
  - ``rows`` and ``columns`` are quoted reserved-ish identifiers in
    several SQL dialects. We follow the planner's recommendation and
    use ``rows_count`` / ``columns_count`` for the column name; the
    manifest / API key remains ``rows`` / ``columns``. The mapping is
    declared in the ORM (radivault_central/db/models.py) and the
    search executor schema.

Tier-2 / Tier-3 (KVP extras / TR / TE / kernel / orientation /
patient_position) are intentionally NOT in this revision — they have
their own follow-on dev-spec ticket per §13.

Dialect notes
-------------
- Postgres path: real ``ADD COLUMN`` per SQL standard.
- SQLite (test runs): ``ADD COLUMN`` is supported for nullable cols
  without server defaults; we use Numeric (-> NUMERIC) and SmallInteger
  / Integer which all map cleanly.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_pixel_spatial_fields"
down_revision = "0010_jpg_preview_defacing"
branch_labels = None
depends_on = None


# Tier-1 series columns (9 new). The manifest -> column mapping is
# applied by the central ingest router; here we only need the SQL
# names. See dev-spec FR-PSF-4.3.
_TIER1_SERIES_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("photometric_interpretation", sa.String(length=20)),
    ("pixel_spacing_x", sa.Numeric(7, 4)),
    ("pixel_spacing_y", sa.Numeric(7, 4)),
    ("slice_thickness_mm", sa.Numeric(7, 4)),
    ("rows_count", sa.Integer()),
    ("columns_count", sa.Integer()),
    ("bits_allocated", sa.SmallInteger()),
    ("bits_stored", sa.SmallInteger()),
    ("frame_of_reference_uid_pseudo", sa.String(length=64)),
    ("kvp", sa.Numeric(5, 1)),
]


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    bind = op.get_bind()
    for col_name, col_type in _TIER1_SERIES_COLUMNS:
        if not _column_exists(bind, "series", col_name):
            op.add_column(
                "series",
                sa.Column(col_name, col_type, nullable=True),
            )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    bind = op.get_bind()
    for col_name, _ in reversed(_TIER1_SERIES_COLUMNS):
        if _column_exists(bind, "series", col_name):
            op.drop_column("series", col_name)
