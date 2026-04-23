"""``POST /v1/search/studies`` + ``GET /v1/search/studies/{uid}`` (dev-spec §7.1/§7.2)."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from radivault_search.audit.search_event import write_audit
from radivault_search.auth.middleware import require_buyer
from radivault_search.errors import QueryTooBroad
from radivault_search.query.cursor import compute_filter_sha256
from radivault_search.query.executor import load_study_detail, run_search
from radivault_search.query.schema import (
    SearchRequest,
    SearchStudyDetail,
    filter_fields_list,
)
from radivault_search.query.schema import canonical_filter_dict as _canon
from radivault_search.query.validator import estimate_cost, validate_filter
from radivault_search.telemetry import (
    EMPTY_RESULT_TOTAL,
    QUERY_TOO_BROAD_TOTAL,
    RESULT_SIZE,
    SEARCH_DURATION,
)

log = logging.getLogger("radivault_search.search")

router = APIRouter()


@router.post("/v1/search/studies")
async def search_studies(
    request: Request,
    body: SearchRequest,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    buyer_pk, buyer_id, tier, kid = require_buyer(request)
    start = time.perf_counter()
    settings = request.app.state.settings
    factory = request.app.state.session_factory
    scope_json = getattr(request.state, "scope_json", {}) or {}

    # Stage 1 — filter length gates (FR-17).
    validate_filter(body)

    filter_dict = _canon(body)
    filter_sha = compute_filter_sha256(filter_dict, salt=settings.auth.global_filter_salt)
    filter_fields = filter_fields_list(body)

    # Stage 2 — cost estimator (FR-21..FR-22).
    with factory() as session:
        estimate = estimate_cost(
            session,
            body,
            max_rows=settings.cost.max_estimated_rows,
            facet_suppress_rows=settings.cost.facet_auto_suppress_rows,
            scope_json=scope_json,
        )
        if estimate.estimated_rows > settings.cost.max_estimated_rows:
            QUERY_TOO_BROAD_TOTAL.inc()
            _schedule_audit(
                background_tasks,
                factory=factory,
                buyer_pk=buyer_pk,
                kid=kid,
                endpoint="/v1/search/studies",
                filter_sha256=filter_sha,
                filter_json_sha256=filter_sha,
                result_count=None,
                cache_hit=False,
                status_code=422,
                error_code="ERR_QUERY_TOO_BROAD",
                latency_ms=int((time.perf_counter() - start) * 1000),
                request_id=request.state.request_id,
                cursor_presence=bool(body.cursor),
            )
            raise QueryTooBroad(
                detail=(
                    f"estimated rows {estimate.estimated_rows:,} exceeds "
                    f"limit {settings.cost.max_estimated_rows:,}"
                ),
                hint="try adding modality or study_date_shifted filters",
            )

        # Stage 3 — executor.
        result = run_search(
            session,
            body,
            buyer_pk=buyer_pk,
            global_salt=settings.auth.global_filter_salt,
            facets_suppressed=estimate.suppressed_facets,
            scope_json=scope_json,
        )

    payload = result.response.model_dump(mode="json")

    duration_ms = int((time.perf_counter() - start) * 1000)
    SEARCH_DURATION.labels(
        tier=tier,
        endpoint="/v1/search/studies",
        status="200",
        has_facets=str(body.include_facets and not estimate.suppressed_facets).lower(),
    ).observe(duration_ms / 1000.0)
    RESULT_SIZE.labels(tier=tier).observe(len(result.response.items))
    if not result.response.items:
        EMPTY_RESULT_TOTAL.labels(buyer_id_hash=_hash_buyer_id(buyer_id)).inc()

    log.info(
        "search_ok",
        extra={
            "event": "search.ok",
            "request_id": request.state.request_id,
            "buyer_id_hash": _hash_buyer_id(buyer_id),
            "tier": tier,
            "endpoint": "/v1/search/studies",
            "status": 200,
            "duration_ms": duration_ms,
            "result_count": len(result.response.items),
            "cache_hit": False,
            "cursor_presence": bool(body.cursor),
            "filter_sha256": filter_sha,
            "filter_fields": filter_fields,
        },
    )

    _schedule_audit(
        background_tasks,
        factory=factory,
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint="/v1/search/studies",
        filter_sha256=filter_sha,
        filter_json_sha256=filter_sha,
        result_count=len(result.response.items),
        cache_hit=False,
        status_code=200,
        error_code=None,
        latency_ms=duration_ms,
        request_id=request.state.request_id,
        cursor_presence=bool(body.cursor),
    )

    return JSONResponse(status_code=200, content=payload)


@router.get("/v1/search/studies/{pseudo_study_uid}")
async def get_study_detail(
    request: Request,
    pseudo_study_uid: str,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    buyer_pk, _buyer_id, tier, kid = require_buyer(request)
    start = time.perf_counter()
    settings = request.app.state.settings
    factory = request.app.state.session_factory

    with factory() as session:
        detail: SearchStudyDetail = load_study_detail(
            session,
            pseudo_study_uid,
            buyer_pk=buyer_pk,
            global_salt=settings.auth.global_filter_salt,
        )

    duration_ms = int((time.perf_counter() - start) * 1000)
    SEARCH_DURATION.labels(
        tier=tier,
        endpoint="/v1/search/studies/{uid}",
        status="200",
        has_facets="false",
    ).observe(duration_ms / 1000.0)

    _schedule_audit(
        background_tasks,
        factory=factory,
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint="/v1/search/studies/{uid}",
        filter_sha256=None,
        filter_json_sha256=None,
        result_count=1,
        cache_hit=False,
        status_code=200,
        error_code=None,
        latency_ms=duration_ms,
        request_id=request.state.request_id,
        cursor_presence=False,
    )
    return JSONResponse(status_code=200, content=detail.model_dump(mode="json"))


# ---------------------------------------------------------------------------


def _schedule_audit(background_tasks: BackgroundTasks, *, factory, **kwargs) -> None:
    background_tasks.add_task(write_audit, factory, **kwargs)


def _hash_buyer_id(buyer_id: str) -> str:
    import hashlib

    return hashlib.sha256(buyer_id.encode("utf-8")).hexdigest()[:12]
