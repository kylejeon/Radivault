"""Pydantic v2 manifest schema (dev-spec §6.5).

The schema is a **superset** of the Gateway Agent v0.1 manifest — it requires
``anonymization_flag`` in addition to everything Gateway already sends. See
Gateway dev-spec §6.4 and Central dev-spec §13 (delta D-3) for the cross-team
contract.

dev-spec-metadata-thumbnail-ingest §6.1 — manifest schema v2 ADDITIVE fields:
``body_part_examined``, ``patient_sex``, ``patient_age_bucket``,
``manufacturer``, ``manufacturer_model_name``, ``study_date_shifted``,
``study_year``, ``series[]``, ``thumbnail`` (base64-embedded JPEG bytes).
``manifest_version`` is widened to allow ``2`` so v1 callers remain accepted.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeidBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    ruleset_version: str
    salt_version: int
    method_code_sequence: list[str] = Field(min_length=1)


class ManifestFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    filename: str
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    bytes: int = Field(ge=0)


class AuditRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    seq: int
    hash: str


class SeriesEntryV2(BaseModel):
    """v2 series array entry (FR-META-1).

    text-search-description Phase 1.5 (FR-TS15-5) — adds optional
    ``series_description`` field (scrubbed by gateway, stored in
    ``series.series_description`` central column). The legacy
    ``series_description_clean`` field is retained for backward
    compatibility with the metadata-thumbnail-ingest contract.
    """

    model_config = ConfigDict(extra="allow")

    pseudo_series_uid: str
    modality: str | None = None
    n_instances: int = Field(ge=0)
    body_part: str | None = None
    series_description_clean: str | None = None
    series_description: str | None = Field(default=None, max_length=200)
    slice_thickness_mm: float | None = None
    kvp: float | None = None


class ThumbnailV2(BaseModel):
    """v2 thumbnail object (FR-META-1, FR-THUMB-2).

    Carries the base64-encoded JPEG payload inline so the wire format remains a
    single multipart manifest part. ~30KB / study is well below the 1 MB
    manifest cap. Central decodes ``data_b64`` and PUTs to MinIO under
    ``radivault-preview/thumbnails/{pseudo_study_uid}.jpg``.
    """

    model_config = ConfigDict(extra="allow")

    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    bytes: int = Field(ge=1, le=1_048_576)
    format: Literal["JPEG"] = "JPEG"
    width: int = 256
    height: int = 256
    source_instance_uid_pseudo: str | None = None
    slice_index: int | None = None
    slice_count: int | None = None
    phi_scrub_status: Literal["passed", "skipped_burned_in", "skipped_unknown"]
    phi_scrub_method: str = "burned_in_tag_gate"
    data_b64: str  # base64 of JPEG payload


class PreviewFrameEntry(BaseModel):
    """jpg-preview-defacing FR-PREVIEW-13 — single frame manifest row.

    Mirrors the ``dicom_preview_frame`` table 1:1 so the central ingest
    router can do a straight INSERT. ``minio_key`` is bucket-relative
    (``previews/{study}/{series}/{idx:04d}.jpg``) — see FR-PREVIEW-10.
    """

    model_config = ConfigDict(extra="allow")

    frame_idx: int = Field(ge=0)
    minio_key: str = Field(min_length=1, max_length=255)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    byte_size: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    phi_scrub_method: str = Field(min_length=1, max_length=40)
    source_instance_uid_pseudo: str | None = Field(default=None, max_length=64)


class PreviewSeriesEntry(BaseModel):
    """jpg-preview-defacing FR-PREVIEW-12 — per-series preview summary.

    Drives the UPDATE on ``series.preview_*`` columns + INSERT on
    ``phi_scrub_audit``. ``frames`` is empty when ``preview_status`` is
    ``skipped|quarantined|pending`` (FR-DEFACE-8).
    """

    model_config = ConfigDict(extra="allow")

    pseudo_series_uid: str = Field(min_length=1, max_length=64)
    series_num: int = Field(ge=1)
    modality: str = Field(min_length=1, max_length=8)
    body_part: str | None = Field(default=None, max_length=32)
    preview_status: Literal["generated", "skipped", "quarantined", "pending"]
    deface_decision: (
        Literal["required", "not_required", "skipped_unsupported_modality"] | None
    ) = None
    deface_decision_reason: str = Field(min_length=1, max_length=255)
    phi_scrub_method: str = Field(min_length=1, max_length=40)
    frame_count: int = Field(ge=0)
    frames: list[PreviewFrameEntry] = Field(default_factory=list)
    sidecar_image_tag: str | None = Field(default=None, max_length=64)
    afni_version: str | None = Field(default=None, max_length=32)
    duration_ms: int | None = None
    outcome: Literal[
        "success",
        "quarantine_input",
        "quarantine_runtime",
        "skipped",
        "not_required",
    ]
    error_code: str | None = Field(default=None, max_length=40)
    error_detail: str | None = Field(default=None, max_length=2000)


class PreviewBatch(BaseModel):
    """jpg-preview-defacing FR-PREVIEW-1 — top-level manifest.preview block."""

    model_config = ConfigDict(extra="allow")

    skipped: bool = False
    reason: str | None = Field(default=None, max_length=64)
    pipeline_version: str = Field(default="0.1.0", max_length=32)
    series: list[PreviewSeriesEntry] = Field(default_factory=list)


class Manifest(BaseModel):
    """Canonical ingest manifest (dev-spec §6.5).

    v1 + v2 (metadata-thumbnail-ingest FR-META-1) shape — additive only.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    manifest_version: int
    gateway_id: str
    hospital_id: str
    pseudo_study_uid: str
    modalities: list[str] = Field(min_length=1)
    n_instances: int = Field(ge=1)
    total_bytes: int = Field(ge=0)
    deid: DeidBlock
    anonymization_flag: str
    files: list[ManifestFile] = Field(min_length=1)
    generated_at: str
    audit_ref: AuditRef | None = None

    # v2 additive — all Optional so v1 manifests remain valid.
    body_part_examined: str | None = None
    patient_sex: Literal["M", "F", "O"] | None = None
    patient_age_bucket: str | None = None  # "30-34", "90+"
    patient_age: int | None = None
    manufacturer: str | None = Field(default=None, max_length=64)
    manufacturer_model_name: str | None = Field(default=None, max_length=128)
    study_date_shifted: str | None = None  # ISO YYYY-MM-DD
    study_year: int | None = None
    n_series: int | None = None  # derived; None on v1
    series: list[SeriesEntryV2] = Field(default_factory=list)
    thumbnail: ThumbnailV2 | None = None

    # text-search-description Phase 1.5 (FR-TS15-5) — manifest v2.1 additive.
    # All Optional so v2.0 manifests remain valid (NFR-TS15-COMPAT-1).
    study_description: str | None = Field(default=None, max_length=200)
    protocol_name: str | None = Field(default=None, max_length=200)
    description_scrub_metadata: dict | None = None

    # buyer-search-v3 FR-V3-DATA-2 — KCD-8 heuristic (modality + body_part)
    # populated by gateway extract.py (lookup_kcd) and persisted onto the
    # study row by central ingest. All Optional for backward compat with
    # pre-v3 manifests; new ingests always populate (Z00.0 fallback when
    # the (modality, body_part) tuple has no rule). Length caps mirror the
    # DB columns: kcd_code VARCHAR(10), kcd_label_* VARCHAR(200).
    kcd_code: str | None = Field(default=None, max_length=10)
    kcd_label_ko: str | None = Field(default=None, max_length=200)
    kcd_label_en: str | None = Field(default=None, max_length=200)

    # jpg-preview-defacing FR-PREVIEW-1 — manifest v2.2 additive. The
    # gateway preview_pipeline emits a per-study block describing every
    # series's deface decision, frame_count, MinIO keys, and audit hint.
    # Central's ingest router persists this into series.preview_*,
    # dicom_preview_frame, phi_scrub_audit. All fields optional so
    # gateways without the flag (FR-PREVIEW-3) still produce valid
    # manifests.
    preview: PreviewBatch | None = None

    @field_validator("anonymization_flag")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip()

    def primary_modality(self) -> str | None:
        if not self.modalities:
            return None
        return self.modalities[0]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ManifestMetadataOnly(Manifest):
    """Metadata-only ingest manifest (Flow A — dev-spec ARCHITECTURE.md §4).

    Relaxes :class:`Manifest` so the Gateway can stream the study's metadata
    without the DICOM pixel payload. The schema still asserts every field the
    full-payload manifest asserts (including ``anonymization_flag`` D-3), but
    ``files`` may be empty and ``n_instances`` may be 0. Downstream callers
    build the study row in ``central.study`` with
    ``central_object_present=False`` so the fulfillment subsystem treats the
    row as cold storage that must be pulled from the gateway at order time.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    n_instances: int = Field(ge=0)
    files: list[ManifestFile] = Field(default_factory=list, min_length=0)
