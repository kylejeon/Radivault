"""Buyer preview endpoints (dev-spec-buyer-browse-preview FR-API-1).

Three endpoints, all behind the buyer-auth middleware:

    GET  /v1/studies/{study_uid}/thumbnail
    GET  /v1/studies/{study_uid}/series/{series_num}/frames/{frame_num}
    POST /v1/studies/{study_uid}/sample-download

Note on placement (deviation from dev-spec FR-API-1)
----------------------------------------------------
The spec literally says "Central neuvre 3 endpoint", but the
``radivault_central`` middleware is hospital-bearer auth (gateway
agents) — it has no buyer API key validator. The ``rv_live_*`` keys
that buyers use already terminate at the ``radivault_search`` middleware
(``BuyerAuthMiddleware``), which also already has DB read access to
``study`` and a Redis client suitable for quota counters. Placing the
preview router here therefore reuses three pieces of infrastructure
verbatim. The BFF env var name (``CENTRAL_INGEST_URL`` vs
``SEARCH_URL``) is the only thing the spec assumed; we wire the BFF
through ``SEARCH_URL`` instead.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Path, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from radivault_central.db.models import SampleDownloadAudit, Study
from radivault_search.audit.search_event import write_audit
from radivault_search.auth.middleware import require_buyer
from radivault_search.errors import (
    FrameNotFound,
    PresignFailed,
    PreviewNotVerified,
    QuotaExceededError,
    SampleInstanceMissing,
    StudyNotFound,
)
from radivault_search.preview.quota import (
    QuotaExceeded,
    QuotaUnavailable,
    incr_and_check,
    peek,
)
from radivault_search.preview.storage import (
    PreviewObjectNotFound,
    PreviewStorageError,
    frame_key,
    sample_key,
    thumbnail_key,
)

log = logging.getLogger("radivault_search.preview.router")

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _study_or_404(session, study_uid: str) -> Study:
    study = session.scalar(select(Study).where(Study.pseudo_study_uid == study_uid))
    if study is None:
        raise StudyNotFound(detail=f"pseudo_study_uid={study_uid!r} not found")
    return study


def _verified_or_403(study: Study) -> None:
    """Enforce the PHI verification gate (FR-PREVIEW-3 invariant)."""
    if study.preview_status != "verified":
        # All non-verified statuses (pending / phi_detected / not_applicable)
        # produce the same 403 — we don't leak the distinction to buyers.
        raise PreviewNotVerified(
            detail=(
                f"study {study.pseudo_study_uid!r} preview_status="
                f"{study.preview_status!r}"
            ),
            hint="Try a verified sample study (5 available in demo).",
        )


def _client_ip(request: Request) -> str | None:
    # Behind a reverse proxy the BFF should already strip X-Forwarded-For
    # to a trusted hop. Audit log treats this as best-effort.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",", 1)[0].strip() or None
    if request.client is not None:
        return request.client.host
    return None


def _etag_for(parts: list[str]) -> str:
    raw = "|".join(parts).encode("utf-8")
    return f'"{hashlib.sha256(raw).hexdigest()[:32]}"'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/studies/{study_uid}/thumbnail")
async def get_thumbnail(
    request: Request,
    study_uid: str,
    background_tasks: BackgroundTasks,
) -> StreamingResponse:
    """Stream the 256x256 JPEG thumbnail for a verified study (FR-API-1)."""
    buyer_pk, _buyer_id, _tier, kid = require_buyer(request)
    started = time.perf_counter()
    factory = request.app.state.session_factory
    store = request.app.state.preview_store

    with factory() as session:
        study = _study_or_404(session, study_uid)
        _verified_or_403(study)
        key = study.preview_thumbnail_key or thumbnail_key(study_uid)

    try:
        body, etag_inner = store.get_jpeg(key)
    except PreviewObjectNotFound as exc:
        raise FrameNotFound(detail=f"thumbnail object missing: {key}") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    etag = _etag_for([study_uid, key, etag_inner])
    headers = {
        "Cache-Control": "public, max-age=86400, immutable",
        "ETag": etag,
        "Content-Length": str(len(body)),
    }

    _audit_async(
        background_tasks,
        factory=factory,
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint="/v1/studies/{uid}/thumbnail",
        result_count=1,
        status_code=200,
        latency_ms=duration_ms,
        request_id=request.state.request_id,
    )

    def _stream():
        # Single-chunk stream is fine for ~30 KB JPEG.
        yield body

    return StreamingResponse(_stream(), media_type="image/jpeg", headers=headers)


@router.get("/v1/studies/{study_uid}/series/{series_num}/frames/{frame_num}")
async def get_frame(
    request: Request,
    background_tasks: BackgroundTasks,
    study_uid: str = Path(...),
    series_num: int = Path(..., ge=1),
    frame_num: int = Path(..., ge=1),
) -> StreamingResponse:
    """Stream a JPEG preview frame (FR-API-1)."""
    buyer_pk, _buyer_id, _tier, kid = require_buyer(request)
    started = time.perf_counter()
    factory = request.app.state.session_factory
    store = request.app.state.preview_store

    with factory() as session:
        study = _study_or_404(session, study_uid)
        _verified_or_403(study)

        slice_count = study.preview_slice_count or 0
        if frame_num > slice_count:
            raise FrameNotFound(
                detail=(
                    f"frame {frame_num} exceeds slice count {slice_count} "
                    f"for study {study_uid!r}"
                )
            )

    key = frame_key(study_uid, series_num, frame_num)
    try:
        body, etag_inner = store.get_jpeg(key)
    except PreviewObjectNotFound as exc:
        raise FrameNotFound(
            detail=(
                f"frame object missing — series={series_num} frame={frame_num}"
            )
        ) from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    etag = _etag_for([study_uid, str(series_num), str(frame_num), etag_inner])
    headers = {
        "Cache-Control": "public, max-age=86400, immutable",
        "ETag": etag,
        "Content-Length": str(len(body)),
    }

    _audit_async(
        background_tasks,
        factory=factory,
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint="/v1/studies/{uid}/series/{n}/frames/{m}",
        result_count=1,
        status_code=200,
        latency_ms=duration_ms,
        request_id=request.state.request_id,
    )

    def _stream():
        yield body

    return StreamingResponse(_stream(), media_type="image/jpeg", headers=headers)


@router.post("/v1/studies/{study_uid}/sample-download")
async def post_sample_download(
    request: Request,
    study_uid: str,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Issue a presigned URL for the sample DICOM (FR-API-1, FR-DOWNLOAD-1)."""
    buyer_pk, _buyer_id, _tier, kid = require_buyer(request)
    started = time.perf_counter()
    factory = request.app.state.session_factory
    store = request.app.state.preview_store
    redis_client = request.app.state.redis
    daily_limit = int(
        getattr(request.app.state, "sample_download_daily_limit", 1)
    )

    with factory() as session:
        study = _study_or_404(session, study_uid)
        _verified_or_403(study)

        if not study.sample_instance_uid:
            raise SampleInstanceMissing(
                detail=(
                    f"study {study.pseudo_study_uid!r} has no sample_instance_uid"
                )
            )
        instance_uid = study.sample_instance_uid

    # Step 1: quota check (atomic INCR + EXPIRE).
    try:
        quota_state = incr_and_check(
            redis_client, buyer_pk, daily_limit=daily_limit
        )
    except QuotaExceeded as exc:
        # Audit the rejected attempt (status 429) before raising so we
        # have a record of quota-blocked tries for compliance review.
        duration_ms = int((time.perf_counter() - started) * 1000)
        _audit_async(
            background_tasks,
            factory=factory,
            buyer_pk=buyer_pk,
            kid=kid,
            endpoint="/v1/studies/{uid}/sample-download",
            result_count=0,
            status_code=429,
            error_code="ERR_QUOTA_EXCEEDED",
            latency_ms=duration_ms,
            request_id=request.state.request_id,
        )
        raise QuotaExceededError(
            detail=(
                f"daily limit {daily_limit} reached for buyer_pk={buyer_pk}"
            ),
            hint="Resets at 00:00 KST.",
        ) from exc
    except QuotaUnavailable as exc:
        # Quota infra unavailable ⇒ fail-closed (do NOT issue a presigned
        # URL with no quota guarantee). Map to ERR_PRESIGN_FAILED so the
        # UI surfaces a transient error.
        log.warning(
            "quota_backend_unavailable",
            extra={"event": "preview.quota_unavailable", "buyer_pk": buyer_pk},
        )
        raise PresignFailed(detail=f"quota backend unavailable: {exc}") from exc

    # Step 2: presign + measure size for response envelope.
    key = sample_key(study_uid, instance_uid)
    try:
        presigned_url, size_bytes = store.presign_get(key, ttl_seconds=3600)
    except PreviewObjectNotFound as exc:
        raise SampleInstanceMissing(
            detail=f"sample DICOM object missing: {key}"
        ) from exc
    except PreviewStorageError as exc:
        raise PresignFailed(detail=f"presign failed: {exc}") from exc

    expires_at_dt = datetime.now(tz=timezone.utc) + timedelta(seconds=3600)
    expires_at_iso = expires_at_dt.isoformat().replace("+00:00", "Z")

    # Step 3: persist audit (sample_download_audit + audit chain).
    presigned_hash = hashlib.sha256(presigned_url.encode("utf-8")).hexdigest()
    with factory() as session:
        audit_row = SampleDownloadAudit(
            buyer_pk=buyer_pk,
            study_uid=study_uid,
            instance_uid=instance_uid,
            presigned_url_hash=presigned_hash,
            requested_at=datetime.now(tz=timezone.utc),
            expires_at=expires_at_dt,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            status="issued",
        )
        session.add(audit_row)
        session.commit()

    duration_ms = int((time.perf_counter() - started) * 1000)
    _audit_async(
        background_tasks,
        factory=factory,
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint="/v1/studies/{uid}/sample-download",
        result_count=1,
        status_code=200,
        latency_ms=duration_ms,
        request_id=request.state.request_id,
    )

    payload = {
        "presigned_url": presigned_url,
        "expires_at": expires_at_iso,
        "instance_uid": instance_uid,
        "study_uid": study_uid,
        "size_bytes": int(size_bytes),
        # K-3 default — quota_after on the same envelope so the UI can
        # update the "Today: N/limit" indicator without a second round-trip.
        "quota_after": {
            "used": quota_state.used,
            "limit": quota_state.limit,
            "resets_at": quota_state.resets_at_iso,
        },
    }
    return JSONResponse(status_code=200, content=payload)


@router.get("/v1/account/quota")
async def get_quota(request: Request) -> JSONResponse:
    """Inspect (do NOT increment) today's sample-download quota."""
    buyer_pk, _buyer_id, _tier, _kid = require_buyer(request)
    redis_client = request.app.state.redis
    daily_limit = int(
        getattr(request.app.state, "sample_download_daily_limit", 1)
    )
    try:
        state = peek(redis_client, buyer_pk, daily_limit=daily_limit)
    except QuotaUnavailable:
        # Soft-fail: return 0/limit so the UI doesn't hard-error.
        return JSONResponse(
            status_code=200,
            content={
                "daily_used": 0,
                "daily_limit": daily_limit,
                "resets_at": None,
                "available": False,
            },
        )
    return JSONResponse(
        status_code=200,
        content={
            "daily_used": state.used,
            "daily_limit": state.limit,
            "resets_at": state.resets_at_iso,
            "available": True,
        },
    )


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


def _audit_async(
    background_tasks: BackgroundTasks,
    *,
    factory,
    buyer_pk: int,
    kid: str,
    endpoint: str,
    result_count: int | None,
    status_code: int,
    latency_ms: int,
    request_id: str,
    error_code: str | None = None,
) -> None:
    """Schedule a search_audit row insert — same pattern as search router."""
    background_tasks.add_task(
        write_audit,
        factory,
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint=endpoint,
        filter_sha256=None,
        filter_json_sha256=None,
        result_count=result_count,
        cache_hit=False,
        status_code=status_code,
        error_code=error_code,
        latency_ms=latency_ms,
        request_id=request_id,
        cursor_presence=False,
    )


__all__ = ["router"]
