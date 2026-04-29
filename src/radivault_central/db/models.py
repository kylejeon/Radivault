"""SQLAlchemy ORM for dev-spec §6.2 / §6.3 / §6.4 schema.

Notes on spec deviations (documented intentionally — dev-spec §9.4 "implementer
may use psycopg sync"):

- SQLAlchemy 2.0 **sync** is used (psycopg v3) instead of async asyncpg. The
  dev-spec itself called this out as an acceptable simplification.
- Partitioning (PARTITION BY RANGE) is not expressed at the ORM level. The
  Alembic migration creates plain tables for v0.1; the dev-spec accepts this
  for SQLite/Postgres-lite test environments while still running the same code
  against a partitioned Postgres schema in production.
"""

from __future__ import annotations

from datetime import datetime

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
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

# SQLite does not autoincrement BIGINT; use Integer on sqlite via variant so
# tests run against an in-memory DB while prod still uses 64-bit identities.
BigId = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    """Common declarative base for Central Ingest ORM classes."""


def _json_type() -> type:
    """JSONB on Postgres, generic JSON elsewhere (SQLite test runs)."""
    return JSONB().with_variant(JSON(), "sqlite")


class Hospital(Base):
    __tablename__ = "hospital"
    __table_args__ = (Index("idx_hospital_active", "active"),)

    hospital_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    hospital_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False, default="KR-SE")
    # buyer-search-v3 FR-V3-DATA-3 — buyer-facing region pseudo (e.g. "SEOUL-A").
    # Distinct from ``region`` (internal ISO code). Index ``idx_hospital_region_pseudo``
    # added by alembic 0007.
    region_pseudo: Mapped[str | None] = mapped_column(String(20))
    salt_version_current: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allowed_ruleset_versions: Mapped[list | None] = mapped_column(_json_type())
    max_study_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=21474836480
    )  # 20 GB
    max_instances_per_study: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    max_concurrent_uploads: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    daily_byte_quota: Mapped[int | None] = mapped_column(BigInteger)
    monthly_byte_quota: Mapped[int | None] = mapped_column(BigInteger)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tokens: Mapped[list[AuthToken]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )


class AuthToken(Base):
    __tablename__ = "auth_token"
    __table_args__ = (
        UniqueConstraint("token_kid", name="uq_auth_token_kid"),
        Index(
            "idx_auth_token_hospital_active",
            "hospital_pk",
        ),
    )

    token_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    token_kid: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String)

    hospital: Mapped[Hospital] = relationship(back_populates="tokens")


class PatientPseudo(Base):
    __tablename__ = "patient_pseudo"
    __table_args__ = (
        UniqueConstraint("hospital_pk", "pseudo_patient_key", name="uq_patient_pseudo_hp"),
    )

    patient_pseudo_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    pseudo_patient_key: Mapped[str] = mapped_column(String, nullable=False)
    age_bucket: Mapped[int | None] = mapped_column(SmallInteger)
    # buyer-search-v3 FR-V3-DATA-1 — exact integer 0-120. Deprecates ``age_bucket``
    # (kept for backward compat through v0.2). CHECK constraint added by alembic
    # 0007 on Postgres.
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(1))
    offset_days_hash: Mapped[str | None] = mapped_column(String)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Study(Base):
    __tablename__ = "study"
    __table_args__ = (
        Index("idx_study_modality_bodypart", "modality", "body_part"),
        Index("idx_study_date", "study_date_shifted"),
        Index("idx_study_patient", "patient_pseudo_pk"),
        Index("idx_study_hospital_ingested", "hospital_pk", "ingested_at"),
        Index("idx_study_manufacturer", "manufacturer"),
        # buyer-search-v3 FR-V3-DATA-2 — KCD facet aggregation + filter index.
        Index("idx_study_kcd_code", "kcd_code"),
    )

    study_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    pseudo_study_uid: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    patient_pseudo_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("patient_pseudo.patient_pseudo_pk")
    )
    modality: Mapped[str | None] = mapped_column(String)
    body_part: Mapped[str | None] = mapped_column(String)
    study_date_shifted: Mapped[datetime | None] = mapped_column(DateTime)
    manufacturer: Mapped[str | None] = mapped_column(String)
    model_name: Mapped[str | None] = mapped_column(String)
    n_instances: Mapped[int] = mapped_column(Integer, nullable=False)
    n_series: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    raw_dicom_tags: Mapped[dict | None] = mapped_column(_json_type())
    central_job_id: Mapped[str] = mapped_column(String, nullable=False)
    gateway_id: Mapped[str] = mapped_column(String, nullable=False)
    # order-fulfillment §14 C-1 (additive): Hot Storage hit marker.
    # Default False; central-ingest will flip to True on successful ingest
    # in a follow-up revision. Safe to keep False during v0.1 — the
    # fulfillment lookup simply treats every study as cold and fans out a
    # transfer_job, which is the correct fallback.
    central_object_present: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # buyer-search-v3 FR-V3-DATA-2 — KCD-8 (한국표준질병사인분류) heuristic mapping.
    # Populated by Gateway extract (modality + body_part lookup) or
    # ``backfill_v3_kcd_age_region.py``. Default fallback row "Z00.0" /
    # "일반 의학적 검사" / "General medical examination" when no rule matches.
    kcd_code: Mapped[str | None] = mapped_column(String(10))
    kcd_label_ko: Mapped[str | None] = mapped_column(String(200))
    kcd_label_en: Mapped[str | None] = mapped_column(String(200))

    # text-search-description Phase 1.5 (FR-TS15-6) — scrubbed free-text
    # description fields. NULL allowed for two distinct semantics:
    #   - feature flag off / pre-Phase-1.5 ingest -> NULL
    #   - description scrubbed but all tokens stripped -> "" (empty string)
    # Search executor's tsvector treats both via coalesce(...,'').
    study_description: Mapped[str | None] = mapped_column(String(200))
    protocol_name: Mapped[str | None] = mapped_column(String(200))

    # dev-spec-buyer-browse-preview FR-DATA-1: PHI verification gate +
    # preview cache pointers + sample download SOPInstanceUID.
    #
    # ``preview_status`` enum:
    #   - 'pending' (default — no preview rendered yet, the safe default
    #     so existing rows are silently excluded from preview surfaces)
    #   - 'verified' — manual or Presidio OCR pass; thumbnail/frames/
    #     sample-download endpoints will return 200 for this row
    #   - 'phi_detected' — operator alert; all preview surfaces return 403
    #   - 'not_applicable' — modality not previewable (e.g. SR/SEG)
    preview_status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending", server_default="pending"
    )
    preview_thumbnail_key: Mapped[str | None] = mapped_column(String)
    preview_slice_count: Mapped[int | None] = mapped_column(Integer)
    sample_instance_uid: Mapped[str | None] = mapped_column(String)


class SampleDownloadAudit(Base):
    """Per-buyer sample DICOM download audit (dev-spec-buyer-browse-preview FR-DATA-1).

    Distinct from order-fulfillment ``download_event``: sample-downloads do
    NOT create an order row, transfer_job, or order_outbox entry — they are
    a separate self-serve trial path. The presigned URL is stored only as a
    SHA-256 hash so a DB leak cannot resurrect the capability.
    """

    __tablename__ = "sample_download_audit"
    __table_args__ = (
        Index("idx_sample_dl_audit_buyer_time", "buyer_pk", "requested_at"),
        Index("idx_sample_dl_audit_study", "study_uid", "requested_at"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    # Logical FK only — search.buyer lives in a different module/schema in
    # production; we don't enforce a cross-DB constraint.
    buyer_pk: Mapped[int] = mapped_column(BigInteger, nullable=False)
    study_uid: Mapped[str] = mapped_column(String, nullable=False)
    instance_uid: Mapped[str] = mapped_column(String, nullable=False)
    presigned_url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="issued", server_default="issued"
    )


class Series(Base):
    __tablename__ = "series"
    __table_args__ = (
        Index("idx_series_study", "study_pk"),
        Index("idx_series_modality", "modality"),
        Index("ix_series_preview_status", "preview_status"),
    )

    series_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    study_pk: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pseudo_series_uid: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    modality: Mapped[str | None] = mapped_column(String)
    body_part: Mapped[str | None] = mapped_column(String)
    series_number: Mapped[int | None] = mapped_column(Integer)
    n_instances: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_dicom_tags: Mapped[dict | None] = mapped_column(_json_type())
    # text-search-description Phase 1.5 (FR-TS15-6) — per-series scrubbed
    # description. Mirrors study.study_description NULL semantics.
    series_description: Mapped[str | None] = mapped_column(String(200))

    # dev-spec-pixel-spatial-fields FR-PSF-4.3 (alembic 0011) — Tier-1
    # series-level pixel/spatial fields. All NULL-allowed; legacy rows
    # ingested before manifest v3 keep ``NULL`` until re-sync. Columns
    # ``rows_count`` / ``columns_count`` are renamed from the DICOM
    # attribute names ``Rows`` / ``Columns`` to dodge SQL reserved-word
    # quoting friction (Q-PSF-7 default).
    photometric_interpretation: Mapped[str | None] = mapped_column(String(20))
    pixel_spacing_x: Mapped[float | None] = mapped_column(Numeric(7, 4))
    pixel_spacing_y: Mapped[float | None] = mapped_column(Numeric(7, 4))
    slice_thickness_mm: Mapped[float | None] = mapped_column(Numeric(7, 4))
    rows_count: Mapped[int | None] = mapped_column(Integer)
    columns_count: Mapped[int | None] = mapped_column(Integer)
    bits_allocated: Mapped[int | None] = mapped_column(SmallInteger)
    bits_stored: Mapped[int | None] = mapped_column(SmallInteger)
    frame_of_reference_uid_pseudo: Mapped[str | None] = mapped_column(String(64))
    kvp: Mapped[float | None] = mapped_column(Numeric(5, 1))

    # jpg-preview-defacing FR-PREVIEW-12 (alembic 0010). New ingestions only:
    # legacy series rows keep ``preview_status='pending'`` and are auto-404'd
    # by the buyer BFF (FR-NEWONLY-2). The dev-spec uses logical name
    # ``dicom_series`` for this table; the actual table name is ``series``.
    preview_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    preview_frame_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    preview_deface_decision: Mapped[str | None] = mapped_column(String(40))
    preview_deface_method: Mapped[str | None] = mapped_column(String(40))
    preview_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    preview_pipeline_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="0.1.0", server_default="0.1.0"
    )


class DicomPreviewFrame(Base):
    """Per-frame preview metadata (jpg-preview-defacing FR-PREVIEW-13).

    One row per generated JPG frame. Holds the MinIO key, sha256 (for
    integrity audit FR-PREVIEW-8), and the per-frame ``phi_scrub_method``
    so the BFF manifest endpoint can answer ``preview_status / frame_count``
    in a single SELECT against this table.
    """

    __tablename__ = "dicom_preview_frame"
    __table_args__ = (
        UniqueConstraint(
            "pseudo_series_uid", "frame_idx", name="uq_dpf_series_frame"
        ),
        Index("ix_dpf_study", "pseudo_study_uid"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    pseudo_series_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    pseudo_study_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    frame_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    minio_key: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    phi_scrub_method: Mapped[str] = mapped_column(String(40), nullable=False)
    source_instance_uid_pseudo: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PhiScrubAudit(Base):
    """Series-level audit row of every defacing pipeline invocation
    (jpg-preview-defacing FR-AUDIT-1 / FR-AUDIT-2).

    ``error_detail`` is varchar(2000) but MUST NOT contain PHI
    (FR-AUDIT-3 / AC-19). The pipeline only writes scrubbed sidecar
    error codes / version strings here.
    """

    __tablename__ = "phi_scrub_audit"
    __table_args__ = (
        Index("ix_psa_study", "pseudo_study_uid"),
        Index("ix_psa_series", "pseudo_series_uid"),
        Index("ix_psa_outcome", "outcome"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    pseudo_study_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    pseudo_series_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    modality: Mapped[str] = mapped_column(String(8), nullable=False)
    body_part: Mapped[str | None] = mapped_column(String(32))
    deface_decision: Mapped[str] = mapped_column(String(40), nullable=False)
    deface_decision_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    phi_scrub_method: Mapped[str] = mapped_column(String(40), nullable=False)
    sidecar_image_tag: Mapped[str | None] = mapped_column(String(64))
    afni_version: Mapped[str | None] = mapped_column(String(32))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_detail: Mapped[str | None] = mapped_column(String(2000))
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Instance(Base):
    __tablename__ = "instance"
    __table_args__ = (Index("idx_instance_series", "series_pk"),)

    instance_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    series_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("series.series_pk"), nullable=False
    )
    pseudo_sop_uid: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sop_class_uid: Mapped[str | None] = mapped_column(String)
    instance_number: Mapped[int | None] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class AuditIngestEvent(Base):
    __tablename__ = "audit_ingest_event"
    __table_args__ = (
        Index("idx_aie_hospital_time", "hospital_pk", "received_at"),
        Index("idx_aie_event", "event"),
    )

    event_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    gateway_id: Mapped[str] = mapped_column(String, nullable=False)
    central_job_id: Mapped[str | None] = mapped_column(String)
    event: Mapped[str] = mapped_column(String, nullable=False)
    pseudo_study_uid: Mapped[str | None] = mapped_column(String)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    bytes_received: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditAnchor(Base):
    __tablename__ = "audit_anchor"
    __table_args__ = (
        UniqueConstraint("hospital_pk", "seq_lo", "seq_hi", name="uq_audit_anchor_range"),
        UniqueConstraint("hospital_pk", "head_hash", name="uq_audit_anchor_hash"),
        CheckConstraint("seq_lo <= seq_hi", name="ck_audit_anchor_order"),
        Index("idx_anchor_hospital_time", "hospital_pk", "anchored_at"),
    )

    anchor_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    gateway_id: Mapped[str] = mapped_column(String, nullable=False)
    seq_lo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seq_hi: Mapped[int] = mapped_column(BigInteger, nullable=False)
    head_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    anchored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditDailyDigest(Base):
    __tablename__ = "audit_daily_digest"
    __table_args__ = (UniqueConstraint("digest_date", "hospital_pk", name="uq_audit_daily_digest"),)

    digest_pk: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    digest_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), nullable=False
    )
    anchor_count: Mapped[int] = mapped_column(Integer, nullable=False)
    digest_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    object_lock_key: Mapped[str | None] = mapped_column(String)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestIdempotencyMirror(Base):
    __tablename__ = "ingest_idempotency_mirror"
    __table_args__ = (Index("idx_idemp_mirror_time", "first_seen_at"),)

    key: Mapped[str] = mapped_column(String, primary_key=True)
    hospital_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hospital.hospital_pk"), primary_key=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    response_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str | None] = mapped_column(String)
