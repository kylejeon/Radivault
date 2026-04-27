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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
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
    # H-5 / dev-spec §6.2 — composite PK (audit_pk, created_at) makes the
    # table PARTITION BY RANGE(created_at) ready. Partitioning itself lands
    # in v0.1.1 (pg_partman), but the PK shape is fixed here so no data
    # migration is needed at that point.
    #
    # Portability note: SQLite cannot do ``AUTOINCREMENT`` on a composite PK
    # column, so on that dialect ``audit_pk`` falls back to a single-column
    # PK (declared via mapped_column primary_key=True). On PostgreSQL the
    # Alembic migration 0002 DROPs the single PK and re-establishes it as
    # ``(audit_pk, created_at)``; see ``alembic/versions/0002_metadata_index.py``
    # for the canonical forward-ready PG shape.
    __table_args__ = (
        Index("idx_search_audit_buyer_time", "buyer_pk", "created_at"),
        Index("idx_search_audit_filter_sha", "filter_sha256"),
    )

    # autoincrement=True works with single-column PK on SQLite (tests) and
    # with Identity on PG. The ``created_at`` PK member below is only
    # marked ``primary_key`` via a dialect-conditional event so SQLite can
    # still emit ``INTEGER PRIMARY KEY AUTOINCREMENT`` on ``audit_pk`` alone.
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
    # text-search-description FR-TS-10 — search-bar query auditing with PHI scrub.
    # ``raw_query``         — verbatim buyer input, NULL'd by 30-day cron.
    # ``masked_query``      — PHI-scrubbed copy, retained indefinitely.
    # ``phi_flagged_patterns`` — pattern names that matched (no raw values).
    # On Postgres ``phi_flagged_patterns`` is TEXT[]; on SQLite tests it is a
    # plain Text column (JSON-encoded list when written via the repository
    # helper). The variant keeps a single ORM mapping that round-trips on both.
    raw_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    masked_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    phi_flagged_patterns: Mapped[list[str] | str | None] = mapped_column(
        PG_ARRAY(Text).with_variant(Text(), "sqlite"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = ["Base", "Buyer", "BuyerApiKey", "SearchAudit"]
