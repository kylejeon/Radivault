"""SQLAlchemy ORM for dev-spec §6.2/§6.3 search-specific tables.

This module **reuses** ``radivault_central.db.models.Base`` so the two
services share one metadata object. We only declare the three new tables
here (``buyer``, ``buyer_api_key``, ``search_audit``); reads against
``study``, ``series``, ``hospital`` etc. go through the central ORM.

Deviations from dev-spec §6.2:
- ``search_audit`` partitioning is declared at the migration level, not the
  ORM. SQLite tests run against a plain table.
- ``CHAR(64)`` is expressed as ``String(64)`` — dialect-agnostic.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

# Inherit the shared Base from central-ingest so a single Base.metadata holds
# both sets of tables — that is the contract the Alembic env expects.
from radivault_central.db.models import Base

BigId = BigInteger().with_variant(Integer(), "sqlite")


def _json_type() -> type:
    return JSONB().with_variant(JSON(), "sqlite")


class Buyer(Base):
    __tablename__ = "buyer"
    __table_args__ = (Index("idx_buyer_active", "active"),)

    buyer_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    buyer_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact_email: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="preview")
    scope_json: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(String)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    keys: Mapped[list[BuyerApiKey]] = relationship(
        back_populates="buyer", cascade="all, delete-orphan"
    )


class BuyerApiKey(Base):
    __tablename__ = "buyer_api_key"
    __table_args__ = (
        UniqueConstraint("kid", name="uq_buyer_api_key_kid"),
        Index("idx_buyer_api_key_buyer_active", "buyer_pk"),
    )

    key_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    buyer_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey("buyer.buyer_pk"), nullable=False)
    kid: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="preview")
    rate_limit_qps: Mapped[int | None] = mapped_column(Integer)
    rate_limit_daily: Mapped[int | None] = mapped_column(Integer)
    scope_json: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String)

    buyer: Mapped[Buyer] = relationship(back_populates="keys")


class SearchAudit(Base):
    __tablename__ = "search_audit"
    __table_args__ = (
        Index("idx_search_audit_buyer_time", "buyer_pk", "created_at"),
        Index("idx_search_audit_filter_sha", "filter_sha256"),
    )

    audit_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    buyer_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey("buyer.buyer_pk"), nullable=False)
    kid: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    filter_sha256: Mapped[str | None] = mapped_column(String(64))
    filter_json_sha256: Mapped[str | None] = mapped_column(String(64))
    result_count: Mapped[int | None] = mapped_column(BigInteger)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    cursor_presence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["Base", "Buyer", "BuyerApiKey", "SearchAudit"]
