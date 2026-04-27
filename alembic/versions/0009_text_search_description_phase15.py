"""text-search-description Phase 1.5 — description columns + tsvector
re-weight + GIN re-index + study_phi_quarantine_audit.

Revision ID: 0009_text_search_description_phase15
Revises: 0008_text_search_safe_fields
Create Date: 2026-04-26

dev-spec-text-search-description-phase15 §6.1 / FR-TS15-5 / FR-TS15-7 /
FR-TS15-10.

Postgres-only migration. SQLite test runs add the description columns as
plain TEXT (no tsvector / GIN, no audit table) so unit tests keep working.

Schema delta (Postgres):
- ``study.study_description varchar(200) NULL`` (FR-TS15-6)
- ``study.protocol_name varchar(200) NULL``    (FR-TS15-6)
- ``series.series_description varchar(200) NULL`` (FR-TS15-6)
- DROP + recreate ``study.search_text`` with weights
  A = study_description / protocol_name,
  B = body_part / kcd_label_en,
  C = kcd_label_ko / modality,
  D = manufacturer / model_name
- ``CREATE INDEX CONCURRENTLY idx_study_search_text`` on the new tsvector.
- ``CREATE INDEX CONCURRENTLY idx_study_search_trgm`` widened to include
  description columns.
- New ``study_phi_quarantine_audit`` table for FR-TS15-10.

Note on CONCURRENTLY: alembic wraps op.execute in an implicit transaction
when run via the standard runner (env.py uses transaction_per_migration
= True by default). For 250-study demo we keep CONCURRENTLY as documented
in the dev-spec but use ``op.execute("COMMIT")`` to break the autotxn just
before the index DDL — Postgres requires CREATE INDEX CONCURRENTLY to run
outside any transaction. If the env.py is configured for "no autocommit"
this still works because we re-issue COMMIT after each index.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_text_search_phase15"
down_revision = "0008_text_search_safe_fields"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def _index_exists(bind, table: str, index: str) -> bool:
    insp = sa.inspect(bind)
    return index in {ix["name"] for ix in insp.get_indexes(table)}


def _table_exists(bind, table: str) -> bool:
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. Add description columns (both Postgres + SQLite).
    if not _column_exists(bind, "study", "study_description"):
        op.add_column(
            "study", sa.Column("study_description", sa.String(length=200), nullable=True)
        )
    if not _column_exists(bind, "study", "protocol_name"):
        op.add_column(
            "study", sa.Column("protocol_name", sa.String(length=200), nullable=True)
        )
    if not _column_exists(bind, "series", "series_description"):
        op.add_column(
            "series", sa.Column("series_description", sa.String(length=200), nullable=True)
        )

    if not is_pg:
        # SQLite path stops here — tsvector / GIN / pg_trgm don't exist.
        # Still create a stub quarantine_audit table so unit tests can
        # exercise the audit insert path.
        if not _table_exists(bind, "study_phi_quarantine_audit"):
            op.create_table(
                "study_phi_quarantine_audit",
                sa.Column("audit_pk", sa.BigInteger, primary_key=True, autoincrement=True),
                sa.Column("study_pk", sa.BigInteger, nullable=False),
                sa.Column(
                    "quarantined_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.func.now(),
                ),
                sa.Column("scrub_version", sa.Text, nullable=False),
                # SQLite has no native ARRAY — JSON-encoded text instead.
                sa.Column("blacklist_matched", sa.Text, nullable=False, server_default="[]"),
                sa.Column("whitelist_matched", sa.Text, nullable=False, server_default="[]"),
                sa.Column("suspicious_token_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("before_hash", sa.Text, nullable=False),
                sa.Column("after_hash", sa.Text, nullable=False),
                sa.Column("reviewed_by", sa.Text, nullable=True),
                sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("review_decision", sa.Text, nullable=True),
            )
        return

    # --- Postgres path ----------------------------------------------------

    # 2. Recreate study.search_text with new weight allocation. Drop the
    #    GIN index first, then the GENERATED column, then re-add both.
    if _index_exists(bind, "study", "idx_study_search_text"):
        op.execute("DROP INDEX IF EXISTS idx_study_search_text;")
    if _column_exists(bind, "study", "search_text"):
        op.execute("ALTER TABLE study DROP COLUMN search_text;")
    op.execute(
        """
        ALTER TABLE study ADD COLUMN search_text tsvector
          GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(study_description, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(protocol_name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(body_part, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(kcd_label_en, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(kcd_label_ko, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(modality, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(manufacturer, '')), 'D') ||
            setweight(to_tsvector('english', coalesce(model_name, '')), 'D')
          ) STORED;
        """
    )

    # 3. Re-create the search_text GIN index. CONCURRENTLY needs to run
    #    outside any transaction; we end the migration's implicit txn by
    #    issuing COMMIT and re-opening one after.
    op.execute("COMMIT")
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_study_search_text "
        "ON study USING GIN(search_text);"
    )
    op.execute("BEGIN")

    # 4. Re-create the trigram GIN index widened to include description
    #    columns so autocomplete can suggest description tokens too.
    if _index_exists(bind, "study", "idx_study_search_trgm"):
        op.execute("DROP INDEX IF EXISTS idx_study_search_trgm;")
    op.execute("COMMIT")
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_study_search_trgm
          ON study USING GIN(
            (
              coalesce(study_description, '') || ' ' ||
              coalesce(protocol_name, '') || ' ' ||
              coalesce(body_part, '') || ' ' ||
              coalesce(kcd_label_en, '') || ' ' ||
              coalesce(kcd_label_ko, '')
            ) gin_trgm_ops
          );
        """
    )
    op.execute("BEGIN")

    # 5. study_phi_quarantine_audit (FR-TS15-10).
    if not _table_exists(bind, "study_phi_quarantine_audit"):
        op.execute(
            """
            CREATE TABLE study_phi_quarantine_audit (
              audit_pk bigserial PRIMARY KEY,
              study_pk bigint NOT NULL REFERENCES study(study_pk),
              quarantined_at timestamptz NOT NULL DEFAULT NOW(),
              scrub_version text NOT NULL,
              blacklist_matched text[] NOT NULL DEFAULT ARRAY[]::text[],
              whitelist_matched text[] NOT NULL DEFAULT ARRAY[]::text[],
              suspicious_token_count int NOT NULL DEFAULT 0,
              before_hash text NOT NULL,
              after_hash text NOT NULL,
              reviewed_by text NULL,
              reviewed_at timestamptz NULL,
              review_decision text NULL
                CHECK (review_decision IS NULL
                       OR review_decision IN ('release', 'redact', 'delete'))
            );
            """
        )
        op.execute(
            "CREATE INDEX idx_phi_quarantine_study_pk "
            "ON study_phi_quarantine_audit (study_pk);"
        )
        op.execute(
            "CREATE INDEX idx_phi_quarantine_unreviewed "
            "ON study_phi_quarantine_audit (quarantined_at) "
            "WHERE reviewed_at IS NULL;"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. Drop quarantine audit table.
    if _table_exists(bind, "study_phi_quarantine_audit"):
        if is_pg:
            op.execute("DROP INDEX IF EXISTS idx_phi_quarantine_unreviewed;")
            op.execute("DROP INDEX IF EXISTS idx_phi_quarantine_study_pk;")
        op.drop_table("study_phi_quarantine_audit")

    if is_pg:
        # 2. Drop the new search_text + indexes.
        if _index_exists(bind, "study", "idx_study_search_trgm"):
            op.execute("DROP INDEX IF EXISTS idx_study_search_trgm;")
        if _index_exists(bind, "study", "idx_study_search_text"):
            op.execute("DROP INDEX IF EXISTS idx_study_search_text;")
        if _column_exists(bind, "study", "search_text"):
            op.execute("ALTER TABLE study DROP COLUMN IF EXISTS search_text;")

        # 3. Restore Phase 1.0 search_text definition.
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
        op.execute(
            "CREATE INDEX idx_study_search_text ON study USING GIN(search_text);"
        )
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

    # 4. Drop description columns (both dialects).
    if _column_exists(bind, "series", "series_description"):
        op.drop_column("series", "series_description")
    if _column_exists(bind, "study", "protocol_name"):
        op.drop_column("study", "protocol_name")
    if _column_exists(bind, "study", "study_description"):
        op.drop_column("study", "study_description")
