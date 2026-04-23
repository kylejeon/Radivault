"""Gateway-facing transfer-job endpoints (dev-spec §7.6-§7.9)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse, Response

from radivault_fulfillment.auth.gateway import require_gateway
from radivault_fulfillment.errors import JobHospitalMismatch
from radivault_fulfillment.jobs.lease import (
    complete_job,
    fail_job,
    report_progress,
)
from radivault_fulfillment.jobs.long_poll import claim_with_longpoll
from radivault_fulfillment.orders.schema import (
    CompletionReport,
    CompletionResponse,
    FailureReport,
    FailureResponse,
    ProgressReport,
    ProgressResponse,
    TransferJobClaim,
)
from radivault_fulfillment.telemetry import (
    TRANSFER_JOB_CLAIM_TOTAL,
    TRANSFER_JOB_FAILURES_TOTAL,
)

log = logging.getLogger("radivault_fulfillment.routers.gateway_jobs")

router = APIRouter(tags=["gateway-jobs"])


@router.get("/v1/gateway/transfer-jobs")
def claim_transfer_job(
    request: Request,
    wait: int = Query(30, ge=0, le=60),
    max_jobs: int = Query(1, ge=1, le=1),  # v0.1 fixed 1
):
    hospital_pk, hospital_id, gateway_id = require_gateway(request)
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        claim = claim_with_longpoll(
            session,
            hospital_pk=hospital_pk,
            gateway_id=gateway_id,
            lease_ttl_seconds=settings.transfer_job.lease_ttl_seconds,
            wait_seconds=wait,
            redis_client=getattr(request.app.state, "redis", None),
            channel_prefix=settings.redis.long_poll_channel_prefix,
        )
        if claim is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Retry-After": "0"})

        # Defensive: make sure the claim's hospital matches the token (should
        # be guaranteed by the query filter, but spec §4.7 FR-41 asks for it).
        if claim.transfer_job.hospital_pk != hospital_pk:
            raise JobHospitalMismatch()

        from radivault_fulfillment.db.models import Order

        order = session.get(Order, claim.transfer_job.order_pk)
        # Also transition the order FSM to 'fetching' on first claim.
        if order is not None and order.status == "queued":
            from radivault_fulfillment.orders.state_machine import transition

            try:
                transition(
                    session,
                    order_pk=order.order_pk,
                    from_state="queued",
                    to_state="fetching",
                    actor="gateway",
                    event="transfer_job.claimed",
                    actor_ref=gateway_id,
                )
            except Exception:
                # Another claim already moved us past 'queued'; not fatal.
                session.rollback()
                session.begin()

        session.commit()
        session.refresh(claim.transfer_job)
        TRANSFER_JOB_CLAIM_TOTAL.labels(hospital_id=hospital_id).inc()

        order_id = session.get(Order, claim.transfer_job.order_pk).order_id  # type: ignore[union-attr]
        payload = TransferJobClaim(
            transfer_job_id=claim.transfer_job.transfer_job_id,
            order_id=order_id,
            hospital_id=hospital_id,
            studies=list(claim.transfer_job.studies or []),
            lease_expires_at=claim.lease_expires_at,
            ruleset_version_required=claim.transfer_job.ruleset_version_required,
            salt_version_required=claim.transfer_job.salt_version_required,
            cancel_requested=bool(claim.transfer_job.cancel_requested),
        )
        return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))


@router.post(
    "/v1/gateway/transfer-jobs/{transfer_job_id}/progress",
    response_model=ProgressResponse,
)
def progress_endpoint(
    transfer_job_id: str, payload: ProgressReport, request: Request
) -> ProgressResponse:
    hospital_pk, hospital_id, gateway_id = require_gateway(request)
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        new_lease, cancel_requested = report_progress(
            session,
            transfer_job_id=transfer_job_id,
            gateway_id=gateway_id,
            n_fetched=payload.n_fetched,
            n_deided=payload.n_deided,
            n_uploaded=payload.n_uploaded,
            lease_extend=payload.lease_extend,
            lease_ttl_seconds=settings.transfer_job.lease_ttl_seconds,
        )
        session.commit()
    return ProgressResponse(lease_expires_at=new_lease, cancel_requested=cancel_requested)


@router.post(
    "/v1/gateway/transfer-jobs/{transfer_job_id}/complete",
    response_model=CompletionResponse,
)
def complete_endpoint(
    transfer_job_id: str, payload: CompletionReport, request: Request
) -> CompletionResponse:
    hospital_pk, hospital_id, gateway_id = require_gateway(request)
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        job, order_state = complete_job(
            session,
            transfer_job_id=transfer_job_id,
            gateway_id=gateway_id,
            manifest=[e.model_dump() for e in payload.manifest],
        )
        session.commit()
    return CompletionResponse(
        transfer_job_id=job.transfer_job_id,
        state="completed",
        order_state=order_state,
    )


@router.post(
    "/v1/gateway/transfer-jobs/{transfer_job_id}/fail",
    response_model=FailureResponse,
)
def fail_endpoint(
    transfer_job_id: str, payload: FailureReport, request: Request
) -> FailureResponse:
    hospital_pk, hospital_id, gateway_id = require_gateway(request)
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        job, will_retry = fail_job(
            session,
            transfer_job_id=transfer_job_id,
            gateway_id=gateway_id,
            reason_code=payload.reason_code,
            details=payload.details,
            retryable=payload.retryable,
            max_retries=settings.transfer_job.max_retries,
        )
        session.commit()
    TRANSFER_JOB_FAILURES_TOTAL.labels(
        hospital_id=hospital_id, reason_code=payload.reason_code
    ).inc()
    return FailureResponse(
        transfer_job_id=job.transfer_job_id,
        state=job.state,
        attempt_count=job.attempt_count,
        will_retry=will_retry,
    )


__all__ = ["router"]
