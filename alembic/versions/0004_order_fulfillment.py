"""Order Fulfillment v0.1 — 9 tables + study.central_object_present column.

Revision ID: 0004_order_fulfillment
Revises: 0003_de_id_pixel
Create Date: 2026-04-22

Adds the nine tables owned by ``radivault_fulfillment`` (dev-spec
§6.2–§6.4) plus the additive contract delta C-1: a ``central_object_present``
boolean column on the existing ``study`` table (Hot Storage hit marker).

PostgreSQL additions
--------------------
- ``radivault_fulfillment_app`` role + GRANT matrix (dev-spec §6.2).
- ``download_event`` is PARTITION BY RANGE(ts) in production; the composite
  PK ``(event_pk, ts)`` is re-established after the ORM single-column PK
  (matches search_audit pattern in 0002).

SQLite reversibility
--------------------
Role + partitioning are skipped on non-PG dialects so the migration is
round-trippable on in-memory SQLite. Tables are created via
``Base.metadata.create_all`` on the fulfillment subset only (not the full
metadata).
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from radivault_central.db.models import Base as CentralBase  # noqa: F401
from radivault_fulfillment.db.models import (  # noqa: F401
    DownloadEvent,
    Order,
    OrderIdempotencyMirror,
    OrderItem,
    OrderOutbox,
    OrderStateHistory,
    TransferJob,
    TransferJobDeadLetter,
    UnlinkedStudy,
)

revision = "0004_order_fulfillment"
down_revision = "0003_de_id_pixel"
branch_labels = None
depends_on = None


# Ordered so child tables are created after their FK targets.
_NEW_TABLES_IN_ORDER = [
    Order.__table__,
    OrderItem.__table__,
    TransferJob.__table__,
    TransferJobDeadLetter.__table__,
    DownloadEvent.__table__,
    OrderStateHistory.__table__,
    OrderOutbox.__table__,
    UnlinkedStudy.__table__,
    OrderIdempotencyMirror.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # C-1 — additive ``central_object_present`` column on existing study.
    # Only add if the table exists (tests create study via create_all) and
    # the column isn't already there (idempotent re-run).
    if "study" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study")}
        if "central_object_present" not in existing_cols:
            if bind.dialect.name == "sqlite":
                # SQLite ALTER TABLE ADD COLUMN supports a simple default only.
                op.execute(
                    "ALTER TABLE study ADD COLUMN central_object_present "
                    "BOOLEAN NOT NULL DEFAULT 0"
                )
            else:
                op.execute(
                    "ALTER TABLE study ADD COLUMN central_object_present "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )

    CentralBase.metadata.create_all(bind=bind, tables=_NEW_TABLES_IN_ORDER)

    if bind.dialect.name == "postgresql":
        # download_event composite PK (event_pk, ts) — partition-ready.
        op.execute(
            "ALTER TABLE download_event DROP CONSTRAINT IF EXISTS download_event_pkey;"
        )
        op.execute(
            "ALTER TABLE download_event "
            "ADD CONSTRAINT download_event_pkey PRIMARY KEY (event_pk, ts);"
        )

        # Role creation + GRANT matrix — wrapped in DO blocks for idempotency.
        op.execute(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles "
            "WHERE rolname='radivault_fulfillment_app') THEN "
            "CREATE ROLE radivault_fulfillment_app NOINHERIT; "
            "END IF; "
            "END $$;"
        )
        op.execute(
            "ALTER ROLE radivault_fulfillment_app SET statement_timeout = '15s';"
        )
        op.execute("ALTER ROLE radivault_fulfillment_app SET lock_timeout = '2s';")
        op.execute(
            "ALTER ROLE radivault_fulfillment_app "
            "SET idle_in_transaction_session_timeout = '10s';"
        )
        op.execute(
            "GRANT CONNECT ON DATABASE radivault_central TO radivault_fulfillment_app;"
        )
        op.execute("GRANT USAGE ON SCHEMA public TO radivault_fulfillment_app;")
        # central-ingest (read-only)
        op.execute(
            "GRANT SELECT ON study, series, instance, patient_pseudo, hospital, "
            "auth_token TO radivault_fulfillment_app;"
        )
        # metadata-index (read-only)
        op.execute(
            "GRANT SELECT ON buyer, buyer_api_key TO radivault_fulfillment_app;"
        )
        # fulfillment RW tables.
        op.execute(
            'GRANT SELECT, INSERT, UPDATE ON '
            '"order", order_item, transfer_job, order_outbox, unlinked_study, '
            'order_idempotency_mirror TO radivault_fulfillment_app;'
        )
        # Append-only tables.
        op.execute(
            "GRANT SELECT, INSERT ON transfer_job_dead_letter, download_event, "
            "order_state_history TO radivault_fulfillment_app;"
        )


def downgrade() -> None:
    bind = op.get_bind()
    cascade = " CASCADE" if bind.dialect.name == "postgresql" else ""

    # Drop in reverse FK order.
    for table in (
        "order_idempotency_mirror",
        "unlinked_study",
        "order_outbox",
        "order_state_history",
        "download_event",
        "transfer_job_dead_letter",
        "transfer_job",
        "order_item",
        "order",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table}"{cascade}')

    inspector = inspect(bind)
    if "study" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study")}
        if "central_object_present" in existing_cols:
            # SQLite ≥3.35 supports DROP COLUMN; we rely on that version in
            # test environments. On older SQLite this downgrade is no-op on
            # the study column (acceptable — tests never downgrade in-place).
            try:
                op.execute("ALTER TABLE study DROP COLUMN central_object_present")
            except Exception:  # pragma: no cover
                pass

    if bind.dialect.name == "postgresql":
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles "
            "WHERE rolname='radivault_fulfillment_app') THEN "
            "REVOKE ALL ON ALL TABLES IN SCHEMA public "
            "FROM radivault_fulfillment_app; "
            "DROP ROLE radivault_fulfillment_app; "
            "END IF; "
            "EXCEPTION WHEN OTHERS THEN NULL; "
            "END $$;"
        )
