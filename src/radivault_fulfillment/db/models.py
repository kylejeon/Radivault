"""SQLAlchemy ORM for dev-spec §6.2/§6.3/§6.4 order-fulfillment tables.

This module reuses :class:`radivault_central.db.models.Base` so the full
metadata (central + search + fulfillment) registers on a single declarative
registry — the Alembic env uses ``Base.metadata.create_all`` for SQLite tests
and targeted DDL for PostgreSQL migrations.

Portability notes (mirrors central/search):
- ``BigId`` variant: BIGINT on Postgres, INTEGER on SQLite (autoincrement).
- ``JSONB`` with JSON variant on SQLite.
- Partitioning (``download_event`` PARTITION BY RANGE(ts)) is declared at the
  migration level on Postgres only; SQLite tests run on a plain table.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, String as Str

from radivault_central.db.models import Base  # shared declarative registry

BigId = BigInteger().with_variant(Integer(), "sqlite")


def _json_type() -> type:
    return JSONB().with_variant(JSON(), "sqlite")


def _inet_type() -> type:
    # PostgreSQL has INET; SQLite has no native INET — fall back to String.
    return INET().with_variant(Str(), "sqlite")


class Order(Base):
    __tablename__ = "order"
    __table_args__ = (
        Index("idx_order_buyer_status", "buyer_pk", "status"),
        Index("idx_order_submitted_desc", "buyer_pk", "submitted_at"),
        Index("idx_order_status_expires", "status", "expires_at"),
    )

    order_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    buyer_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("buyer.buyer_pk"), nullable=False
    )
    kid: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    status_billing: Mapped[str] = mapped_column(
        String, nullable=False, default="pending_billing"
    )
    n_studies: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_estimated_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    agreement_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    path_type: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    staging_complete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String)
    last_error_detail: Mapped[str | None] = mapped_column(String)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OrderItem(Base):
    __tablename__ = "order_item"
    __table_args__ = (
        UniqueConstraint("order_pk", "pseudo_study_uid", name="uq_order_item_ps"),
        Index("idx_order_item_order", "order_pk"),
        Index("idx_order_item_hospital_state", "hospital_pk", "state"),
    )

    order_item_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    order_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order.order_pk"), nullable=False
    )
    pseudo_study_uid: Mapped[str] = mapped_column(String, nullable=False)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)  # hot_storage|on_demand|mixed
    state: Mapped[str] = mapped_column(String, nullable=False)
    n_instances: Mapped[int | None] = mapped_column(Integer)
    total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    staged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String)


class TransferJob(Base):
    __tablename__ = "transfer_job"
    __table_args__ = (
        UniqueConstraint("order_pk", "hospital_pk", name="uq_transfer_job_order_hosp"),
        Index(
            "idx_transfer_job_hospital_state",
            "hospital_pk",
            "state",
            "created_at",
        ),
        Index("idx_transfer_job_lease_expiry", "lease_expires_at"),
        Index("idx_transfer_job_order", "order_pk"),
    )

    transfer_job_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    transfer_job_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    order_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order.order_pk"), nullable=False
    )
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    state: Mapped[str] = mapped_column(String, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String)
    last_error_detail: Mapped[str | None] = mapped_column(String)
    studies: Mapped[list] = mapped_column(_json_type(), nullable=False)
    n_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_deided: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_uploaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ruleset_version_required: Mapped[str] = mapped_column(String, nullable=False)
    salt_version_required: Mapped[int] = mapped_column(Integer, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TransferJobDeadLetter(Base):
    __tablename__ = "transfer_job_dead_letter"
    __table_args__ = (Index("idx_dlq_unresolved", "dead_at"),)

    dlq_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    transfer_job_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transfer_job.transfer_job_pk"), nullable=False
    )
    dead_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    reason_detail: Mapped[str | None] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String)
    resolution: Mapped[str | None] = mapped_column(String)


class DownloadEvent(Base):
    __tablename__ = "download_event"
    __table_args__ = (
        Index("idx_download_event_buyer_time", "buyer_pk", "ts"),
        Index("idx_download_event_order", "order_pk"),
        Index("idx_download_event_signature", "signature_hash"),
    )

    # Postgres production is PARTITION BY RANGE(ts); SQLite tests use a plain
    # table with a single-column PK. The migration creates the partitioned
    # variant on Postgres only.
    event_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    order_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order.order_pk"), nullable=False
    )
    order_item_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order_item.order_item_pk")
    )
    buyer_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("buyer.buyer_pk"), nullable=False
    )
    kid: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    src_ip: Mapped[str | None] = mapped_column(_inet_type())
    user_agent: Mapped[str | None] = mapped_column(String)
    bytes_transferred: Mapped[int | None] = mapped_column(BigInteger)
    http_status: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    object_key: Mapped[str | None] = mapped_column(String)
    signature_hash: Mapped[str | None] = mapped_column(String(16))
    ttl_seconds: Mapped[int | None] = mapped_column(Integer)


class OrderStateHistory(Base):
    __tablename__ = "order_state_history"
    __table_args__ = (
        Index("idx_order_history_order_time", "order_pk", "at"),
        CheckConstraint(
            "actor in ('buyer','gateway','admin','system','timer')",
            name="ck_order_history_actor",
        ),
    )

    history_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    order_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order.order_pk"), nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String)
    to_state: Mapped[str] = mapped_column(String, nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    actor_ref: Mapped[str | None] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OrderOutbox(Base):
    __tablename__ = "order_outbox"
    __table_args__ = (Index("idx_outbox_undispatched", "created_at"),)

    outbox_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    order_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order.order_pk")
    )
    transfer_job_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transfer_job.transfer_job_pk")
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(_json_type(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String)


class UnlinkedStudy(Base):
    __tablename__ = "unlinked_study"
    __table_args__ = (Index("idx_unlinked_available", "hospital_pk", "detached_at"),)

    unlinked_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    pseudo_study_uid: Mapped[str] = mapped_column(String, nullable=False)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    original_order_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order.order_pk")
    )
    detached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    disposition: Mapped[str] = mapped_column(
        String, nullable=False, default="available_for_reassignment"
    )
    reassigned_to_order_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order.order_pk")
    )
    reassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String)


class OrderIdempotencyMirror(Base):
    __tablename__ = "order_idempotency_mirror"
    __table_args__ = (Index("idx_order_idemp_mirror_time", "first_seen_at"),)

    key: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("buyer.buyer_pk"), primary_key=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    response_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str | None] = mapped_column(String)
    order_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order.order_pk")
    )


__all__ = [
    "Base",
    "DownloadEvent",
    "Order",
    "OrderIdempotencyMirror",
    "OrderItem",
    "OrderOutbox",
    "OrderStateHistory",
    "TransferJob",
    "TransferJobDeadLetter",
    "UnlinkedStudy",
]
