"""Pydantic request/response schemas (dev-spec §6.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    pseudo_study_uids: list[str] = Field(..., min_length=1, max_length=10000)
    agreement_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    notes: str | None = Field(None, max_length=512)
    preferred_download_ttl_hours: int | None = Field(None, ge=1, le=168)


class OrderItemSummary(BaseModel):
    pseudo_study_uid: str
    hospital_opaque_id: str
    source: Literal["hot_storage", "on_demand", "mixed"]
    state: str
    n_instances: int | None = None
    total_bytes: int | None = None


class TransferJobSummary(BaseModel):
    transfer_job_id: str
    hospital_id: str
    state: str
    attempt_count: int
    lease_expires_at: datetime | None = None
    last_error: str | None = None


class OrderResponse(BaseModel):
    order_id: str
    state: str
    state_billing: str
    n_studies: int
    total_bytes: int
    total_estimated_usd: float
    tier: str
    path_type: str | None = None
    submitted_at: datetime
    estimated_ready_at: datetime | None = None
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    cancelled_at: datetime | None = None
    progress: float = 0.0
    eta_seconds: int | None = None
    items: list[OrderItemSummary] = []
    transfer_jobs: list[TransferJobSummary] = []
    last_error: dict | None = None


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    next_cursor: str | None = None
    has_next: bool = False
    page_size: int = 50


class CancelRequest(BaseModel):
    reason: str | None = Field(None, max_length=512)


class CancelResponse(BaseModel):
    order_id: str
    state: str
    cancelled_at: datetime
    refund_eligible: bool = False


class DownloadUrlBatchRequest(BaseModel):
    ttl_seconds: int | None = Field(None, ge=3600, le=604800)


class DownloadFile(BaseModel):
    object_key: str
    bytes: int
    sha256: str
    url: str


class DownloadItem(BaseModel):
    pseudo_study_uid: str
    files: list[DownloadFile]


class DownloadUrlBatch(BaseModel):
    order_id: str
    ttl_seconds: int
    expires_at: datetime
    minted_at: datetime
    items: list[DownloadItem]
    total_bytes: int


# --- Gateway-plane schemas ---------------------------------------------------
class TransferJobClaim(BaseModel):
    transfer_job_id: str
    order_id: str
    hospital_id: str
    studies: list[dict]
    lease_expires_at: datetime
    ruleset_version_required: str
    salt_version_required: int
    cancel_requested: bool = False


class ProgressReport(BaseModel):
    n_fetched: int = Field(..., ge=0)
    n_deided: int = Field(..., ge=0)
    n_uploaded: int = Field(..., ge=0)
    lease_extend: bool = True


class ProgressResponse(BaseModel):
    lease_expires_at: datetime
    cancel_requested: bool = False


class CompletionReportItem(BaseModel):
    pseudo_study_uid: str
    n_instances: int
    total_bytes: int
    status: Literal["uploaded", "skipped", "quarantined"]
    central_job_ids: list[str] = []


class CompletionReport(BaseModel):
    manifest: list[CompletionReportItem]
    audit_ref: dict | None = None


class CompletionResponse(BaseModel):
    transfer_job_id: str
    state: str
    order_state: str


class FailureReport(BaseModel):
    reason_code: Literal[
        "PACS_UNAVAILABLE",
        "DEID_FAILED",
        "UPLOAD_FAILED",
        "BURNED_IN_BLOCKED",
        "OTHER",
    ]
    details: str = Field(..., max_length=2048)
    retryable: bool


class FailureResponse(BaseModel):
    transfer_job_id: str
    state: str
    attempt_count: int
    will_retry: bool


__all__ = [
    "CancelRequest",
    "CancelResponse",
    "CompletionReport",
    "CompletionReportItem",
    "CompletionResponse",
    "DownloadFile",
    "DownloadItem",
    "DownloadUrlBatch",
    "DownloadUrlBatchRequest",
    "FailureReport",
    "FailureResponse",
    "OrderItemSummary",
    "OrderListResponse",
    "OrderRequest",
    "OrderResponse",
    "ProgressReport",
    "ProgressResponse",
    "TransferJobClaim",
    "TransferJobSummary",
]
