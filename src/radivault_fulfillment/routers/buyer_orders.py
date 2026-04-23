"""Buyer-facing order endpoints (dev-spec §7.1-§7.5)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request, status

from radivault_central.db.models import Hospital, Instance, Series, Study
from radivault_fulfillment.auth.buyer import require_buyer
from radivault_fulfillment.cancellation.service import cancel_as_buyer
from radivault_fulfillment.config import Settings
from radivault_fulfillment.db.models import OrderItem, TransferJob
from radivault_fulfillment.download.audit import record_url_minted
from radivault_fulfillment.download.presigned import PresignedSigner
from radivault_fulfillment.errors import (
    OrderAgreementRequired,
    OrderExpired,
    OrderNotFound,
    OrderNotReady,
    OrderTerminal,
    UrlTtlExceeded,
)
from radivault_fulfillment.orders.buyer_phase import buyer_phase_for
from radivault_fulfillment.orders.repository import (
    get_order_for_buyer,
    list_items_for_order,
    list_jobs_for_order,
    list_orders_for_buyer,
)
from radivault_fulfillment.orders.schema import (
    CancelRequest,
    CancelResponse,
    DownloadFile,
    DownloadItem,
    DownloadUrlBatch,
    DownloadUrlBatchRequest,
    OrderItemSummary,
    OrderListResponse,
    OrderRequest,
    OrderResponse,
    TransferJobSummary,
)
from radivault_fulfillment.orders.service import (
    compute_estimated_ready_at,
    create_order,
)
from radivault_fulfillment.orders.validator import validate_order
from radivault_fulfillment.telemetry import (
    ORDER_SUBMISSIONS_TOTAL,
    URL_MINT_TOTAL,
)

log = logging.getLogger("radivault_fulfillment.routers.buyer_orders")

router = APIRouter(tags=["orders"])


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def _tier_config(settings: Settings, tier: str):
    return settings.order.tier_paid if tier == "paid" else settings.order.tier_preview


def _coerce_utc(ts: datetime | None) -> datetime | None:
    """SQLite DATETIME columns come back naive; assume UTC."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def _order_response(
    *,
    order,
    items_summary: list[OrderItemSummary],
    jobs_summary: list[TransferJobSummary],
    estimated_ready_at: datetime | None = None,
) -> OrderResponse:
    progress = 0.0
    if order.n_studies and items_summary:
        ok = sum(1 for it in items_summary if it.state in ("staged", "hot_hit_staged", "copied"))
        progress = ok / order.n_studies
    submitted_at = _coerce_utc(order.submitted_at)
    ready_at = _coerce_utc(order.ready_at)
    expires_at = _coerce_utc(order.expires_at)
    cancelled_at = _coerce_utc(order.cancelled_at)
    est = _coerce_utc(estimated_ready_at)
    now = datetime.now(tz=UTC)
    return OrderResponse(
        order_id=order.order_id,
        state=order.status,
        buyer_phase=buyer_phase_for(order.status),
        state_billing=order.status_billing,
        n_studies=order.n_studies,
        total_bytes=order.total_bytes,
        total_estimated_usd=float(order.total_estimated_usd),
        tier=order.tier,
        path_type=order.path_type,
        submitted_at=submitted_at or now,
        estimated_ready_at=est,
        ready_at=ready_at,
        expires_at=expires_at,
        cancelled_at=cancelled_at,
        progress=progress,
        eta_seconds=(int((est - now).total_seconds()) if est and est > now else None),
        items=items_summary,
        transfer_jobs=jobs_summary,
        last_error=(
            {"code": order.last_error_code, "detail": order.last_error_detail}
            if order.last_error_code
            else None
        ),
    )


def _item_summary(item: OrderItem, *, hospital_ids: dict[int, str]) -> OrderItemSummary:
    hospital_opaque_id = hospital_ids.get(item.hospital_pk, f"hosp_{item.hospital_pk}")
    return OrderItemSummary(
        pseudo_study_uid=item.pseudo_study_uid,
        hospital_opaque_id=hospital_opaque_id,
        source=item.source if item.source in ("hot_storage", "on_demand", "mixed") else "on_demand",
        state=item.state,
        n_instances=item.n_instances,
        total_bytes=item.total_bytes,
    )


def _job_summary(job: TransferJob, *, hospital_ids: dict[int, str]) -> TransferJobSummary:
    return TransferJobSummary(
        transfer_job_id=job.transfer_job_id,
        hospital_id=hospital_ids.get(job.hospital_pk, f"hosp_{job.hospital_pk}"),
        state=job.state,
        attempt_count=job.attempt_count,
        lease_expires_at=job.lease_expires_at,
        last_error=job.last_error_detail,
    )


def _hospital_id_map(session, hospital_pks: set[int]) -> dict[int, str]:
    if not hospital_pks:
        return {}
    rows = (
        session.query(Hospital.hospital_pk, Hospital.hospital_id)
        .filter(Hospital.hospital_pk.in_(hospital_pks))
        .all()
    )
    return {pk: hid for pk, hid in rows}


@router.post(
    "/v1/orders",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=OrderResponse,
)
def create_order_endpoint(payload: OrderRequest, request: Request) -> OrderResponse:
    buyer_pk, buyer_id, tier, kid, scope_json = require_buyer(request)
    settings = _get_settings(request)
    tier_cfg = _tier_config(settings, tier)
    session_factory = request.app.state.session_factory

    if payload.agreement_hash != settings.audit.agreement_hash_current:
        raise OrderAgreementRequired(detail="agreement_hash does not match the current MSA digest")

    with session_factory() as session:
        cohort = validate_order(
            session,
            buyer_pk=buyer_pk,
            tier=tier,
            scope_json=scope_json,
            tier_cfg=tier_cfg,
            pseudo_study_uids=payload.pseudo_study_uids,
        )
        order, items = create_order(
            session,
            buyer_pk=buyer_pk,
            kid=kid,
            tier=tier,
            tier_cfg=tier_cfg,
            cohort=cohort,
            agreement_hash=payload.agreement_hash,
            notes=payload.notes,
            settings=settings,
        )
        session.commit()
        session.refresh(order)
        # Prefetch hospital opaque ids for response.
        hospital_ids = _hospital_id_map(session, cohort.hospital_pks)

    estimated_ready_at = compute_estimated_ready_at(
        submitted_at=order.submitted_at,
        hot=len(cohort.hot_hit),
        cold=len(cohort.cold),
        settings=settings,
    )
    ORDER_SUBMISSIONS_TOTAL.labels(tier=tier, status="accepted").inc()
    return _order_response(
        order=order,
        items_summary=[_item_summary(it, hospital_ids=hospital_ids) for it in items],
        jobs_summary=[],
        estimated_ready_at=estimated_ready_at,
    )


@router.get("/v1/orders", response_model=OrderListResponse)
def list_orders_endpoint(
    request: Request,
    status_filter: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> OrderListResponse:
    buyer_pk, *_ = require_buyer(request)
    session_factory = request.app.state.session_factory

    statuses = None
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
    limit = max(1, min(limit, 200))

    before_submitted_at = None
    before_pk = None
    if cursor:
        # Very simple cursor encoding: ``<iso>|<pk>`` urlsafe b64.
        import base64

        try:
            decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
            iso, pk = decoded.split("|", 1)
            before_submitted_at = datetime.fromisoformat(iso)
            before_pk = int(pk)
        except Exception:
            before_submitted_at = None
            before_pk = None

    with session_factory() as session:
        rows = list_orders_for_buyer(
            session,
            buyer_pk=buyer_pk,
            status=statuses,
            limit=limit + 1,
            before_submitted_at=before_submitted_at,
            before_pk=before_pk,
        )
        hospital_ids: dict[int, str] = {}
        responses: list[OrderResponse] = []
        for order in rows[:limit]:
            items = list_items_for_order(session, order_pk=order.order_pk)
            jobs = list_jobs_for_order(session, order_pk=order.order_pk)
            hps = {it.hospital_pk for it in items} | {j.hospital_pk for j in jobs}
            hospital_ids = _hospital_id_map(session, hps)
            responses.append(
                _order_response(
                    order=order,
                    items_summary=[
                        _item_summary(it, hospital_ids=hospital_ids)
                        for it in items
                        if it.state != "detached"
                    ],
                    jobs_summary=[_job_summary(j, hospital_ids=hospital_ids) for j in jobs],
                )
            )

    has_next = len(rows) > limit
    next_cursor = None
    if has_next and responses:
        import base64

        last = responses[-1]
        raw = f"{last.submitted_at.isoformat()}|{rows[limit - 1].order_pk}"
        next_cursor = base64.urlsafe_b64encode(raw.encode()).decode()
    return OrderListResponse(
        items=responses, next_cursor=next_cursor, has_next=has_next, page_size=len(responses)
    )


@router.get("/v1/orders/{order_id}", response_model=OrderResponse)
def get_order_endpoint(order_id: str, request: Request) -> OrderResponse:
    buyer_pk, *_ = require_buyer(request)
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        order = get_order_for_buyer(session, order_id=order_id, buyer_pk=buyer_pk)
        if order is None:
            raise OrderNotFound()
        items = [
            it
            for it in list_items_for_order(session, order_pk=order.order_pk)
            if it.state != "detached"
        ]
        jobs = list_jobs_for_order(session, order_pk=order.order_pk)
        hps = {it.hospital_pk for it in items} | {j.hospital_pk for j in jobs}
        hospital_ids = _hospital_id_map(session, hps)

    return _order_response(
        order=order,
        items_summary=[_item_summary(it, hospital_ids=hospital_ids) for it in items],
        jobs_summary=[_job_summary(j, hospital_ids=hospital_ids) for j in jobs],
    )


@router.post("/v1/orders/{order_id}/cancel", response_model=CancelResponse, status_code=200)
def cancel_order_endpoint(
    order_id: str, payload: CancelRequest | None, request: Request
) -> CancelResponse:
    buyer_pk, *_ = require_buyer(request)
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        order = get_order_for_buyer(session, order_id=order_id, buyer_pk=buyer_pk)
        if order is None:
            raise OrderNotFound()
        cancelled_at = cancel_as_buyer(
            session,
            order=order,
            reason=(payload.reason if payload else None),
        )
        session.commit()
        return CancelResponse(
            order_id=order.order_id,
            state="cancelled",
            cancelled_at=cancelled_at,
            refund_eligible=False,
        )


@router.post(
    "/v1/orders/{order_id}/download-urls",
    response_model=DownloadUrlBatch,
    status_code=200,
)
def download_urls_endpoint(
    order_id: str, payload: DownloadUrlBatchRequest | None, request: Request
) -> DownloadUrlBatch:
    buyer_pk, buyer_id, tier, kid, _scope_json = require_buyer(request)
    settings = _get_settings(request)
    tier_cfg = _tier_config(settings, tier)
    session_factory = request.app.state.session_factory

    ttl = (payload.ttl_seconds if payload else None) or settings.storage.presign.default_ttl_seconds
    if ttl > tier_cfg.download_ttl_max_seconds:
        raise UrlTtlExceeded(
            detail=f"requested ttl {ttl}s exceeds tier cap {tier_cfg.download_ttl_max_seconds}s"
        )
    if ttl < settings.storage.presign.min_ttl_seconds:
        ttl = settings.storage.presign.min_ttl_seconds
    if ttl > settings.storage.presign.max_ttl_seconds:
        ttl = settings.storage.presign.max_ttl_seconds

    signer: PresignedSigner = request.app.state.presigned_signer

    with session_factory() as session:
        order = get_order_for_buyer(session, order_id=order_id, buyer_pk=buyer_pk)
        if order is None:
            raise OrderNotFound()
        now = datetime.now(tz=UTC)
        if order.status in ("cancelled", "failed"):
            raise OrderTerminal(detail=f"order status={order.status}")
        expires_at_aware = _coerce_utc(order.expires_at)
        if order.status == "expired" or (expires_at_aware and expires_at_aware < now):
            raise OrderExpired()
        if order.status != "ready_for_download":
            raise OrderNotReady(detail=f"order status={order.status}")

        # Join to instances via order_item -> study -> series -> instance.
        items = [
            it
            for it in list_items_for_order(session, order_pk=order.order_pk)
            if it.state != "detached"
        ]

        # Build the download response.
        response_items: list[DownloadItem] = []
        total_bytes = 0
        expires_at = now.replace(microsecond=0)  # will be overwritten below
        src_ip = _client_ip(request)
        user_agent = request.headers.get("User-Agent")
        request_id = getattr(request.state, "request_id", "unknown")

        for item in items:
            study = (
                session.query(Study).filter(Study.pseudo_study_uid == item.pseudo_study_uid).first()
            )
            if study is None:
                continue
            series_rows = session.query(Series).filter(Series.study_pk == study.study_pk).all()
            files: list[DownloadFile] = []
            for series in series_rows:
                inst_rows = (
                    session.query(Instance).filter(Instance.series_pk == series.series_pk).all()
                )
                for inst in inst_rows:
                    minted = signer.mint(
                        object_key=inst.object_key,
                        ttl_seconds=ttl,
                        filename=f"{inst.pseudo_sop_uid}.dcm",
                    )
                    sha_hex = (
                        inst.sha256.hex()
                        if isinstance(inst.sha256, (bytes, bytearray))
                        else str(inst.sha256)
                    )
                    files.append(
                        DownloadFile(
                            object_key=inst.object_key,
                            bytes=inst.bytes,
                            sha256=sha_hex,
                            url=minted.url,
                        )
                    )
                    total_bytes += inst.bytes
                    record_url_minted(
                        session,
                        order_pk=order.order_pk,
                        order_item_pk=item.order_item_pk,
                        buyer_pk=buyer_pk,
                        kid=kid,
                        src_ip=src_ip,
                        user_agent=user_agent,
                        request_id=request_id,
                        object_key=inst.object_key,
                        signature_hash=minted.signature_hash,
                        ttl_seconds=ttl,
                    )

            response_items.append(DownloadItem(pseudo_study_uid=item.pseudo_study_uid, files=files))

        session.commit()

    from datetime import timedelta

    expires_at = datetime.now(tz=UTC) + timedelta(seconds=ttl)
    URL_MINT_TOTAL.labels(tier=tier).inc()
    return DownloadUrlBatch(
        order_id=order.order_id,
        ttl_seconds=ttl,
        expires_at=expires_at,
        minted_at=datetime.now(tz=UTC),
        items=response_items,
        total_bytes=total_bytes,
    )


def _client_ip(request: Request) -> str | None:
    hdr = request.headers.get("X-Forwarded-For")
    if hdr:
        return hdr.split(",")[0].strip()
    client = request.client
    return client.host if client else None


__all__ = ["router"]
