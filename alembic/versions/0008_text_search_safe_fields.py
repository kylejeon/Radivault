"""text-search-description Phase 1.0 — safe-field tsvector + GIN x2 + audit PHI columns.

Revision ID: 0008_text_search_safe_fields
Revises: 0007_v3_kcd_age_region
Create Date: 2026-04-26

dev-spec-text-search-description §6.1 / FR-TS-3 / FR-TS-5 / FR-TS-6 / FR-TS-10.

Postgres-only migration (no SQLite equivalent for tsvector/GIN/pg_trgm). On
SQLite (test runs) every step is short-circuited, so unit tests against the
in-memory engine continue to work — but the FTS path itself only matters in
Postgres production.

Schema delta (Postgres):
- ``CREATE EXTENSION IF NOT EXISTS pg_trgm;``
- ``study.search_text tsvector GENERATED ALWAYS AS (...) STORED``
  weights body_part=A, kcd_label_ko/en=B, modality=C, manufacturer/model_name=D
- ``CREATE INDEX idx_study_search_text ON study USING GIN(search_text);``
- ``CREATE INDEX idx_study_search_trgm ON study USING GIN((coalesce(...)) gin_trgm_ops);``
- ``search_audit.raw_query TEXT NULL`` (30-day retention via cron)
- ``search_audit.masked_query TEXT NULL`` (PHI-scrubbed, infinite retention)
- ``search_audit.phi_flagged_patterns TEXT[] NULL`` (pattern names only)
- ``CREATE INDEX idx_search_audit_raw_age ON search_audit (created_at) WHERE raw_query IS NOT NULL;``
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_text_search_safe_fields"
down_revision = "0007_v3_kcd_age_region"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def _index_exists(bind, table: str, index: str) -> bool:
    insp = sa.inspect(bind)
    return index in {ix["name"] for ix in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if not is_pg:
        # SQLite test runs: tsvector/GIN/pg_trgm don't exist. Add the audit
        # columns as plain TEXT so SQLite-backed unit tests can still exercise
        # the audit insert path with raw/masked/flags populated.
        if not _column_exists(bind, "search_audit", "raw_query"):
            op.add_column("search_audit", sa.Column("raw_query", sa.Text(), nullable=True))
        if not _column_exists(bind, "search_audit", "masked_query"):
            op.add_column("search_audit", sa.Column("masked_query", sa.Text(), nullable=True))
        if not _column_exists(bind, "search_audit", "phi_flagged_patterns"):
            # SQLite has no native ARRAY type — fall back to JSON-encoded text.
            op.add_column(
                "search_audit",
                sa.Column("phi_flagged_patterns", sa.Text(), nullable=True),
            )
        return

    # --- Postgres path ----------------------------------------------------

    # 1. pg_trgm extension (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. study.search_text — GENERATED ALWAYS STORED weighted tsvector.
    if not _column_exists(bind, "study", "search_text"):
        op.execute(
            """
            ALTER TABLE study ADD COLUMN search_text tsvector
              GENERATED ALWAYS AS (
                setweight(to_tsvector('english', coalesce(body_part, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(kcd_label_ko, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(kcd_label_en, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(modality, '')), 'C') ||
                setweight(to_tsvector('english', coalesce(manufacturer, '')), 'D') ||
                setweight(to_tsvector('english', coalesce(model_name, '')), 'D')
              ) STORED;
            """
        )

    # 3. GIN index on search_text (FR-TS-5).
    if not _index_exists(bind, "study", "idx_study_search_text"):
        op.execute(
            "CREATE INDEX idx_study_search_text ON study USING GIN(search_text);"
        )

    # 4. Trigram GIN index for autocomplete + fuzzy (FR-TS-6).
    #    Indexes a concatenation expression — note the matching expression
    #    must be used at query time (or pg_trgm will plan a seq scan).
    if not _index_exists(bind, "study", "idx_study_search_trgm"):
        op.execute(
            """
            CREATE INDEX idx_study_search_trgm ON study USING GIN(
              (
                coalesce(body_part, '') || ' ' ||
                coalesce(kcd_label_en, '') || ' ' ||
                coalesce(kcd_label_ko, '')
              ) gin_trgm_ops
            );
            """
        )

    # 5. search_audit PHI columns (FR-TS-10).
    if not _column_exists(bind, "search_audit", "raw_query"):
        op.add_column("search_audit", sa.Column("raw_query", sa.Text(), nullable=True))
    if not _column_exists(bind, "search_audit", "masked_query"):
        op.add_column("search_audit", sa.Column("masked_query", sa.Text(), nullable=True))
    if not _column_exists(bind, "search_audit", "phi_flagged_patterns"):
        op.execute(
            "ALTER TABLE search_audit ADD COLUMN phi_flagged_patterns TEXT[] NULL;"
        )

    # 6. Partial index to make the 30-day raw_query cleanup cron cheap.
    if not _index_exists(bind, "search_audit", "idx_search_audit_raw_age"):
        op.execute(
            "CREATE INDEX idx_search_audit_raw_age ON search_audit (created_at) "
            "WHERE raw_query IS NOT NULL;"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if not is_pg:
        if _column_exists(bind, "search_audit", "phi_flagged_patterns"):
            op.drop_column("search_audit", "phi_flagged_patterns")
        if _column_exists(bind, "search_audit", "masked_query"):
            op.drop_column("search_audit", "masked_query")
        if _column_exists(bind, "search_audit", "raw_query"):
            op.drop_column("search_audit", "raw_query")
        return

    # --- Postgres path ----------------------------------------------------
    if _index_exists(bind, "search_audit", "idx_search_audit_raw_age"):
        op.execute("DROP INDEX IF EXISTS idx_search_audit_raw_age;")
    if _column_exists(bind, "search_audit", "phi_flagged_patterns"):
        op.execute("ALTER TABLE search_audit DROP COLUMN IF EXISTS phi_flagged_patterns;")
    if _column_exists(bind, "search_audit", "masked_query"):
        op.execute("ALTER TABLE search_audit DROP COLUMN IF EXISTS masked_query;")
    if _column_exists(bind, "search_audit", "raw_query"):
        op.execute("ALTER TABLE search_audit DROP COLUMN IF EXISTS raw_query;")

    if _index_exists(bind, "study", "idx_study_search_trgm"):
        op.execute("DROP INDEX IF EXISTS idx_study_search_trgm;")
    if _index_exists(bind, "study", "idx_study_search_text"):
        op.execute("DROP INDEX IF EXISTS idx_study_search_text;")
    if _column_exists(bind, "study", "search_text"):
        op.execute("ALTER TABLE study DROP COLUMN IF EXISTS search_text;")
    # pg_trgm extension is intentionally NOT dropped — other features may use it.
