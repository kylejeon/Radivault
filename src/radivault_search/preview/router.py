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
from sqlalchemy import func, select

from radivault_central.db.models import (
    DicomPreviewFrame,
    PhiScrubAudit,
    SampleDownloadAudit,
    Series,
    Study,
)
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
    preview_key_v2,
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


_VERIFIED_STATUSES = {"verified", "auto_verified"}


def _verified_or_403(study: Study) -> None:
    """Enforce the PHI verification gate (FR-PREVIEW-3 invariant).

    'verified' = manual OCR/operator gate (D-13 hot-storage 5 sample studies).
    'auto_verified' = ingest-time BurnedInAnnotation=No + de-id chain audit
    (FR-INGEST-1, dev-spec-metadata-thumbnail-ingest §6). Both are buyer-safe.
    """
    if study.preview_status not in _VERIFIED_STATUSES:
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


@router.get("/v1/studies/{study_uid}/preview-manifest")
async def get_preview_manifest(
    request: Request,
    background_tasks: BackgroundTasks,
    study_uid: str = Path(...),
) -> JSONResponse:
    """jpg-preview-defacing FR-API-2 / dev-spec §7.2.

    Returns the per-study preview manifest assembled from
    ``series`` (preview_* columns), ``dicom_preview_frame`` (frame
    counts), and the latest ``phi_scrub_audit`` row per series
    (``deface_method`` + sidecar evidence).

    Legacy / pre-pipeline studies (no rows in ``series`` for this
    pseudo_study_uid) return 404 — that 404 is the explicit signal the
    BFF + ``StudyDetailPanel`` use to keep the legacy SliceViewer
    mounted (design-spec §11.1 silent-coexistence).

    No legacy ``study.preview_status`` gate. The new pipeline already
    deface'd / scrubbed every series before any frame was uploaded, so
    a row in ``series.preview_status='generated'`` is itself the
    safe-to-serve invariant.
    """
    buyer_pk, _buyer_id, _tier, kid = require_buyer(request)
    started = time.perf_counter()
    factory = request.app.state.session_factory

    with factory() as session:
        # Ensure the study exists at all — otherwise 404 (matches §7.1
        # 404 contract). The lookup also makes the 404 vs "legacy study"
        # distinction observable to the BFF: missing study has no row,
        # missing-pipeline study has a row but no series.
        study = _study_or_404(session, study_uid)

        # FR-PREVIEW-12 — series rows. Order by series_number for stable
        # presentation in the FrameSliderViewer chip strip.
        series_rows: list[Series] = list(
            session.scalars(
                select(Series)
                .where(Series.pseudo_study_uid == study_uid)  # type: ignore[attr-defined]
                .order_by(Series.series_number.asc().nulls_last(), Series.series_pk.asc())
            ).all()
        ) if hasattr(Series, "pseudo_study_uid") else []

        # The Series ORM here is keyed by study_pk, not pseudo_study_uid.
        # Resolve via the parent study row's PK.
        if not series_rows:
            series_rows = list(
                session.scalars(
                    select(Series)
                    .where(Series.study_pk == study.study_pk)
                    .order_by(
                        Series.series_number.asc().nulls_last(),
                        Series.series_pk.asc(),
                    )
                ).all()
            )

        # FR-NEWONLY-2: pre-pipeline studies have either zero series rows
        # (legacy ingest path that pre-dates 0008/0009 series migration)
        # OR series rows where every preview_status='pending'. In both
        # cases the manifest endpoint is "unavailable" — the BFF treats
        # the 404 as a legacy fallthrough to the old SliceViewer path.
        new_pipeline_present = any(
            (s.preview_status or "pending") != "pending" or s.preview_frame_count
            for s in series_rows
        )
        if not series_rows or not new_pipeline_present:
            raise StudyNotFound(
                detail=(
                    f"preview manifest unavailable for study "
                    f"{study_uid!r} — legacy / pre-pipeline ingest"
                )
            )

        # FR-PREVIEW-13 — count frames per series (pseudo_series_uid).
        series_uids = [
            s.pseudo_series_uid for s in series_rows if s.pseudo_series_uid
        ]
        frame_counts: dict[str, int] = {}
        if series_uids:
            rows = session.execute(
                select(
                    DicomPreviewFrame.pseudo_series_uid,
                    func.count(DicomPreviewFrame.id),
                )
                .where(DicomPreviewFrame.pseudo_series_uid.in_(series_uids))
                .group_by(DicomPreviewFrame.pseudo_series_uid)
            ).all()
            frame_counts = {uid: int(cnt) for uid, cnt in rows}

        # FR-AUDIT-1 / FR-API-2 — surface the most recent
        # phi_scrub_audit.phi_scrub_method per series so the
        # FrameSliderViewer's DefacePill can render
        # ``afni_refacer_v0_7`` / ``deface_failed_runtime`` etc.
        scrub_methods: dict[str, str] = {}
        if series_uids:
            # SQLite-portable "latest per group" via correlated max(id).
            sub = (
                select(
                    PhiScrubAudit.pseudo_series_uid,
                    func.max(PhiScrubAudit.id).label("max_id"),
                )
                .where(PhiScrubAudit.pseudo_series_uid.in_(series_uids))
                .group_by(PhiScrubAudit.pseudo_series_uid)
                .subquery()
            )
            rows = session.execute(
                select(
                    PhiScrubAudit.pseudo_series_uid,
                    PhiScrubAudit.phi_scrub_method,
                ).join(sub, PhiScrubAudit.id == sub.c.max_id)
            ).all()
            scrub_methods = {uid: method for uid, method in rows}

        # Build response payload. Fall back gracefully when scrub_method
        # is missing (e.g. flag-off ingest that wrote a series row but
        # no audit row): use ``preview_deface_method`` from the series
        # row, which alembic 0010 keeps in sync.
        body_series: list[dict] = []
        for s in series_rows:
            uid = s.pseudo_series_uid
            preview_status = s.preview_status or "pending"
            # Skip purely-legacy pending rows even when other series in
            # the same study are generated — they would render as
            # disabled chips in the FrameSliderViewer per design-spec
            # §6.2 "all-quarantined fallback" but here we just suppress
            # noise for the 99% case.
            if preview_status == "pending" and not s.preview_frame_count:
                continue
            method = (
                scrub_methods.get(uid)
                or s.preview_deface_method
                or "none_required"
            )
            body_series.append(
                {
                    "pseudo_series_uid": uid,
                    "series_num": s.series_number,
                    "modality": s.modality,
                    "body_part": s.body_part,
                    "frame_count": int(
                        frame_counts.get(uid, s.preview_frame_count or 0)
                    ),
                    "status": preview_status,
                    "scrub_method": method,
                    "deface_decision": s.preview_deface_decision,
                    "first_frame_url": (
                        f"/api/studies/{study_uid}/series/{s.series_number}"
                        f"/frames/0"
                        if s.series_number is not None
                        and preview_status == "generated"
                        else None
                    ),
                }
            )

    if not body_series:
        # Every series row was 'pending' with frame_count=0 — equivalent
        # to "no manifest available" for the BFF.
        raise StudyNotFound(
            detail=(
                f"preview manifest empty for study {study_uid!r} — "
                f"no generated/skipped/quarantined series"
            )
        )

    # FR-API-2: §7.2 envelope.
    payload = {
        "pseudo_study_uid": study_uid,
        "pipeline_version": "0.1.0",
        "deface_method": (
            # study-level summary: pick the first non-None deface_method
            # so the UI can render a study-wide pill if it wants.
            next(
                (
                    s["scrub_method"]
                    for s in body_series
                    if s["scrub_method"] not in (None, "none_required")
                ),
                "none_required",
            )
        ),
        "series": body_series,
    }

    duration_ms = int((time.perf_counter() - started) * 1000)
    _audit_async(
        background_tasks,
        factory=factory,
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint="/v1/studies/{uid}/preview-manifest",
        result_count=len(body_series),
        status_code=200,
        latency_ms=duration_ms,
        request_id=request.state.request_id,
    )
    return JSONResponse(
        status_code=200,
        content=payload,
        headers={"Cache-Control": "private, max-age=60"},
    )


def _new_pipeline_lookup(session, study_uid: str, series_num: int, frame_idx_zero: int):
    """jpg-preview-defacing FR-API-1 / FR-PREVIEW-10.

    Resolve a (study_uid, series_num, 0-based frame_idx) tuple into the
    new-pipeline ``radivault-previews`` MinIO key by joining
    ``series`` + ``dicom_preview_frame``. Returns ``None`` if no row
    exists — caller falls through to the legacy bucket.
    """
    series = session.execute(
        select(Series.pseudo_series_uid, Series.preview_status)
        .join(Study, Study.study_pk == Series.study_pk)
        .where(
            Study.pseudo_study_uid == study_uid,
            Series.series_number == series_num,
        )
    ).first()
    if series is None:
        return None
    pseudo_series_uid, preview_status = series
    frame_row = session.execute(
        select(DicomPreviewFrame.minio_key)
        .where(
            DicomPreviewFrame.pseudo_series_uid == pseudo_series_uid,
            DicomPreviewFrame.frame_idx == frame_idx_zero,
        )
    ).first()
    if frame_row is None:
        # The series was registered under the new pipeline (we found
        # the series row) but this specific frame is missing — surface
        # as 404 with the preview_status so the UI can reason about it.
        return ("missing", preview_status, pseudo_series_uid)
    return ("hit", frame_row[0], pseudo_series_uid)


@router.get("/v1/studies/{study_uid}/series/{series_num}/frames/{frame_num}")
async def get_frame(
    request: Request,
    background_tasks: BackgroundTasks,
    study_uid: str = Path(...),
    series_num: int = Path(..., ge=1),
    frame_num: int = Path(..., ge=1),
) -> StreamingResponse:
    """Stream a JPEG preview frame (FR-API-1).

    Two code paths share this endpoint:

    1. **New pipeline** (B-4 fix): when ``dicom_preview_frame`` has a row
       for ``(pseudo_series_uid, frame_idx = frame_num - 1)`` we serve
       from the new ``radivault-previews`` bucket using the gateway-
       written key. NO legacy ``study.preview_status='verified'`` gate —
       the gateway preview_pipeline already AFNI-defaced + PHI-scrubbed
       every JPG before upload, so the per-series
       ``preview_status='generated'`` is the right invariant.

    2. **Legacy** (pre-jpg-preview-defacing seeded studies): when no
       ``dicom_preview_frame`` row exists for this study the route falls
       through to the original ``frames/{study}/{series}/{n}.jpg`` key
       in the legacy ``radivault-preview`` bucket and the original
       study-level ``_verified_or_403`` gate fires. This keeps the 5
       hot-storage demo studies rendering exactly as before.
    """
    buyer_pk, _buyer_id, _tier, kid = require_buyer(request)
    started = time.perf_counter()
    factory = request.app.state.session_factory
    store = request.app.state.preview_store
    previews_store = getattr(request.app.state, "previews_store_v2", None) or store

    new_pipeline_lookup = None
    with factory() as session:
        study = _study_or_404(session, study_uid)
        # frame_num is 1-based on the wire (matches §7.1 + sibling BFF
        # route). Translate to 0-based ``frame_idx`` for the new bucket
        # key layout (FR-PREVIEW-10).
        new_pipeline_lookup = _new_pipeline_lookup(
            session, study_uid, series_num, frame_num - 1
        )
        if new_pipeline_lookup is None:
            # Legacy path — apply the original gates.
            _verified_or_403(study)

            slice_count = study.preview_slice_count or 0
            if frame_num > slice_count:
                raise FrameNotFound(
                    detail=(
                        f"frame {frame_num} exceeds slice count {slice_count} "
                        f"for study {study_uid!r}"
                    )
                )

    if new_pipeline_lookup is not None:
        kind = new_pipeline_lookup[0]
        if kind == "missing":
            _, preview_status, _series = new_pipeline_lookup
            raise FrameNotFound(
                detail=(
                    f"preview_unavailable — series {series_num} frame "
                    f"{frame_num} status={preview_status!r}"
                )
            )
        # Hit — kind == "hit", second element is the bucket key.
        key = new_pipeline_lookup[1]
        try:
            body, etag_inner = previews_store.get_jpeg(key)
        except PreviewObjectNotFound as exc:
            # Sidecar wrote the row but the bucket doesn't have the
            # blob — treat as 404 not 500 (matches §7.1 frame_unavailable).
            raise FrameNotFound(
                detail=(
                    f"frame object missing in radivault-previews — "
                    f"series={series_num} frame={frame_num}"
                )
            ) from exc
    else:
        # Legacy path key + bucket.
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
