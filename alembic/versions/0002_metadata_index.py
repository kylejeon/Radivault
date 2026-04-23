"""Metadata Index v0.1 — buyer, buyer_api_key, search_audit + study composite indexes.

Revision ID: 0002_metadata_index
Revises: 0001_initial
Create Date: 2026-04-22

Adds the three new tables owned by ``radivault_search`` plus the three study
composite indexes for keyset pagination / facet queries (dev-spec §6.2 / §6.3,
FR-67). On PostgreSQL we also create the ``radivault_buyer_ro`` and
``search_admin`` roles with the GRANT matrix from dev-spec §6.2.

On SQLite (test runs) the role-creation SQL is skipped so the migration is
fully reversible on an in-memory DB. Table structure is created via
``Base.metadata.create_all`` on the subset we own, matching the 0001 pattern.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from radivault_central.db.models import Base as CentralBase  # noqa: F401 — registry side-effect
from radivault_search.db.models import (  # noqa: F401
    Buyer,
    BuyerApiKey,
    SearchAudit,
)

revision = "0002_metadata_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


_NEW_TABLES = ["buyer", "buyer_api_key", "search_audit"]

# dev-spec §6.3 — 3 composite indexes on the existing study table.
_STUDY_INDEXES = [
    (
        "idx_study_date_keyset",
        "study",
        ["study_date_shifted", "study_pk"],
    ),
    (
        "idx_study_filter_keyset",
        "study",
        ["modality", "body_part", "study_date_shifted", "study_pk"],
    ),
    (
        "idx_study_ingested_keyset",
        "study",
        ["ingested_at", "study_pk"],
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    # Create only the tables this revision introduces — not the whole metadata.
    tables_to_create = [
        Buyer.__table__,
        BuyerApiKey.__table__,
        SearchAudit.__table__,
    ]
    CentralBase.metadata.create_all(bind=bind, tables=tables_to_create)

    # Composite indexes on the pre-existing study table.
    inspector = inspect(bind)
    existing = {ix["name"] for ix in inspector.get_indexes("study")}
    for name, table, cols in _STUDY_INDEXES:
        if name in existing:
            continue
        op.create_index(name, table, cols)

    if bind.dialect.name == "postgresql":
        # H-5 — promote ``search_audit`` PK to ``(audit_pk, created_at)`` so
        # the table can be PARTITIONed BY RANGE(created_at) in v0.1.1 without
        # a data migration. SQLAlchemy emits a single-column PK by default
        # (necessary for SQLite autoincrement); here we swap it on PG.
        op.execute(
            "ALTER TABLE search_audit DROP CONSTRAINT IF EXISTS search_audit_pkey;"
        )
        op.execute(
            "ALTER TABLE search_audit "
            "ADD CONSTRAINT search_audit_pkey PRIMARY KEY (audit_pk, created_at);"
        )

        # Role creation + GRANTs (dev-spec §6.2). Wrapped in DO blocks so
        # re-running the migration is idempotent.
        op.execute(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='radivault_buyer_ro') THEN "
            "CREATE ROLE radivault_buyer_ro NOINHERIT; "
            "END IF; "
            "END $$;"
        )
        op.execute(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='search_admin') THEN "
            "CREATE ROLE search_admin NOINHERIT; "
            "END IF; "
            "END $$;"
        )
        op.execute(
            "ALTER ROLE radivault_buyer_ro SET statement_timeout = '10s';"
        )
        op.execute(
            "ALTER ROLE radivault_buyer_ro SET lock_timeout = '2s';"
        )
        op.execute(
            "ALTER ROLE radivault_buyer_ro "
            "SET idle_in_transaction_session_timeout = '5s';"
        )
        op.execute("GRANT USAGE ON SCHEMA public TO radivault_buyer_ro;")
        op.execute(
            "GRANT SELECT ON study, series, instance, patient_pseudo, hospital "
            "TO radivault_buyer_ro;"
        )
        op.execute("GRANT SELECT ON buyer, buyer_api_key TO radivault_buyer_ro;")
        # FR-6/7: auth middleware writes ``buyer_api_key.last_used_at`` on
        # every cold-cache success. Grant a *column-level* UPDATE so the
        # buyer-ro role can touch only that single column (minimum-privilege
        # over "full UPDATE on the table"). All other columns remain
        # immutable. dev-spec §6.2 "UPDATE/DELETE 미부여" is preserved for
        # every other column; this is the narrowest possible exception.
        op.execute(
            "GRANT UPDATE (last_used_at) ON buyer_api_key TO radivault_buyer_ro;"
        )
        op.execute("GRANT INSERT ON search_audit TO radivault_buyer_ro;")

        op.execute("GRANT USAGE ON SCHEMA public TO search_admin;")
        op.execute(
            "GRANT SELECT, INSERT, UPDATE ON buyer, buyer_api_key TO search_admin;"
        )
        op.execute("GRANT SELECT ON search_audit TO search_admin;")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {ix["name"] for ix in inspector.get_indexes("study")}
    for name, _table, _cols in _STUDY_INDEXES:
        if name in existing:
            op.drop_index(name, table_name="study")

    # H-5 — if the composite PK was installed, revert to single-column PK
    # before dropping the table. This is best-effort on PG because the
    # table is being dropped anyway; explicit DROP CONSTRAINT keeps the
    # downgrade symmetric with the upgrade and observable in logs.
    if bind.dialect.name == "postgresql":
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name='search_audit' AND constraint_name='search_audit_pkey') THEN "
            "ALTER TABLE search_audit DROP CONSTRAINT search_audit_pkey; "
            "ALTER TABLE search_audit ADD CONSTRAINT search_audit_pkey PRIMARY KEY (audit_pk); "
            "END IF; "
            "EXCEPTION WHEN OTHERS THEN NULL; "
            "END $$;"
        )

    # Drop tables in FK-safe order.
    cascade = " CASCADE" if bind.dialect.name == "postgresql" else ""
    # search_audit FK → buyer, buyer_api_key FK → buyer. Drop dependents first.
    for table in ("search_audit", "buyer_api_key", "buyer"):
        op.execute(f"DROP TABLE IF EXISTS {table}{cascade}")

    if bind.dialect.name == "postgresql":
        # Role drop is best-effort; ignore "role still in use" errors.
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='radivault_buyer_ro') THEN "
            "REVOKE UPDATE (last_used_at) ON buyer_api_key FROM radivault_buyer_ro; "
            "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM radivault_buyer_ro; "
            "DROP ROLE radivault_buyer_ro; "
            "END IF; "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='search_admin') THEN "
            "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM search_admin; "
            "DROP ROLE search_admin; "
            "END IF; "
            "EXCEPTION WHEN OTHERS THEN NULL; "
            "END $$;"
        )
