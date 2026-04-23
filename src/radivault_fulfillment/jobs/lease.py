"""Lease management + reaper (FR-43..FR-59).

Progress / complete / fail / reaper are all implemented here so the route
handlers stay thin.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import (
    OrderOutbox,
    TransferJob,
    TransferJobDeadLetter,
)
from radivault_fulfillment.errors import (
    JobCounterRegress,
    JobLeaseExpired,
    JobLeaseOwnership,
    JobNotFound,
    JobStateConflict,
)

log = logging.getLogger("radivault_fulfillment.jobs.lease")


def _get_job_for_update(session: Session, *, transfer_job_id: str) -> TransferJob:
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    stmt = select(TransferJob).where(TransferJob.transfer_job_id == transfer_job_id)
    if dialect == "postgresql":
        stmt = stmt.with_for_update()
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        raise JobNotFound()
    return row


def _normalize_tz(ts: datetime | None) -> datetime | None:
    """SQLite drops timezone awareness — coerce naive to UTC so comparisons work."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def _check_ownership_and_lease(job: TransferJob, *, gateway_id: str) -> None:
    if job.state != "claimed":
        raise JobStateConflict(detail=f"job state={job.state!r}")
    if job.lease_owner != gateway_id:
        raise JobLeaseOwnership()
    now = datetime.now(tz=UTC)
    lease_expires_at = _normalize_tz(job.lease_expires_at)
    if lease_expires_at is None or lease_expires_at < now:
        raise JobLeaseExpired()


def report_progress(
    session: Session,
    *,
    transfer_job_id: str,
    gateway_id: str,
    n_fetched: int,
    n_deided: int,
    n_uploaded: int,
    lease_extend: bool,
    lease_ttl_seconds: int,
) -> tuple[datetime, bool]:
    """Update counters + optionally extend lease. Returns (lease_expires_at, cancel_requested)."""
    job = _get_job_for_update(session, transfer_job_id=transfer_job_id)
    _check_ownership_and_lease(job, gateway_id=gateway_id)

    if n_fetched < job.n_fetched or n_deided < job.n_deided or n_uploaded < job.n_uploaded:
        raise JobCounterRegress()

    now = datetime.now(tz=UTC)
    new_lease = _normalize_tz(job.lease_expires_at)
    if lease_extend:
        new_lease = now + timedelta(seconds=lease_ttl_seconds)

    session.execute(
        update(TransferJob)
        .where(TransferJob.transfer_job_pk == job.transfer_job_pk)
        .values(
            n_fetched=n_fetched,
            n_deided=n_deided,
            n_uploaded=n_uploaded,
            lease_expires_at=new_lease,
        )
    )
    return new_lease or now, bool(job.cancel_requested)


def complete_job(
    session: Session,
    *,
    transfer_job_id: str,
    gateway_id: str,
    manifest: list[dict],
) -> tuple[TransferJob, str]:
    """Mark job completed + propagate to order_item/order.

    Returns (job, order_state_after). Does NOT commit — caller manages TX.
    """
    from radivault_fulfillment.db.models import Order, OrderItem

    job = _get_job_for_update(session, transfer_job_id=transfer_job_id)
    _check_ownership_and_lease(job, gateway_id=gateway_id)

    # Manifest must cover every pseudo_study_uid in the claim.
    claim_uids = {s.get("pseudo_study_uid") for s in (job.studies or [])}
    manifest_uids = {entry.get("pseudo_study_uid") for entry in manifest}
    missing = claim_uids - manifest_uids
    extra = manifest_uids - claim_uids
    if missing or extra:
        from radivault_fulfillment.errors import JobManifestMismatch

        raise JobManifestMismatch(
            detail=(f"missing={sorted(missing)[:3]} extra={sorted(extra)[:3]}")
        )

    now = datetime.now(tz=UTC)
    session.execute(
        update(TransferJob)
        .where(TransferJob.transfer_job_pk == job.transfer_job_pk)
        .values(state="completed", completed_at=now)
    )

    # Propagate to order_item.
    for entry in manifest:
        session.execute(
            update(OrderItem)
            .where(
                OrderItem.order_pk == job.order_pk,
                OrderItem.pseudo_study_uid == entry["pseudo_study_uid"],
            )
            .values(
                state="staged",
                staged_at=now,
                n_instances=entry.get("n_instances"),
                total_bytes=entry.get("total_bytes"),
            )
        )

    # Compute new order state.
    all_items = (
        session.execute(select(OrderItem).where(OrderItem.order_pk == job.order_pk)).scalars().all()
    )
    staged_states = {"staged", "hot_hit_staged", "copied"}
    if all(item.state in staged_states for item in all_items):
        new_order_state = "staging_complete"
    else:
        new_order_state = "staging_partial"

    order_row = session.execute(select(Order).where(Order.order_pk == job.order_pk)).scalar_one()

    # Only transition if the target is an allowed one for the current state.
    from radivault_fulfillment.orders.state_machine import is_allowed, transition

    if order_row.status in ("queued", "fetching", "staging_partial") and is_allowed(
        order_row.status, new_order_state, "gateway"
    ):
        transition(
            session,
            order_pk=order_row.order_pk,
            from_state=order_row.status,
            to_state=new_order_state,
            actor="gateway",
            event="transfer_job.complete",
            actor_ref=gateway_id,
        )

    # Outbox: when everything is staged, ask the poller to staging_copy + ready.
    if new_order_state == "staging_complete":
        session.add(
            OrderOutbox(
                order_pk=order_row.order_pk,
                event_type="order.ready_staging_copy",
                payload={"order_pk": order_row.order_pk},
            )
        )
    return job, new_order_state


def fail_job(
    session: Session,
    *,
    transfer_job_id: str,
    gateway_id: str,
    reason_code: str,
    details: str,
    retryable: bool,
    max_retries: int,
) -> tuple[TransferJob, bool]:
    """Handle a failure report. Returns (job_after, will_retry)."""
    job = _get_job_for_update(session, transfer_job_id=transfer_job_id)
    if job.lease_owner != gateway_id:
        raise JobLeaseOwnership()
    if job.state not in ("claimed", "queued"):
        raise JobStateConflict(detail=f"state={job.state!r}")

    attempts = job.attempt_count or 0
    now = datetime.now(tz=UTC)
    will_retry = retryable and attempts < max_retries

    if will_retry:
        session.execute(
            update(TransferJob)
            .where(TransferJob.transfer_job_pk == job.transfer_job_pk)
            .values(
                state="queued",
                lease_owner=None,
                lease_expires_at=None,
                last_error_code=reason_code,
                last_error_detail=details,
            )
        )
    else:
        session.execute(
            update(TransferJob)
            .where(TransferJob.transfer_job_pk == job.transfer_job_pk)
            .values(
                state="dead",
                lease_owner=None,
                lease_expires_at=None,
                last_error_code=reason_code,
                last_error_detail=details,
            )
        )
        session.add(
            TransferJobDeadLetter(
                transfer_job_pk=job.transfer_job_pk,
                dead_at=now,
                reason_code=reason_code,
                reason_detail=details,
                attempts=attempts,
            )
        )
        session.add(
            OrderOutbox(
                order_pk=job.order_pk,
                event_type="order.fail",
                payload={"order_pk": job.order_pk, "reason_code": reason_code},
            )
        )
    session.flush()
    session.refresh(job)
    return job, will_retry


def reap_expired_leases(session: Session, *, max_retries: int) -> tuple[int, int]:
    """Re-queue any leased-but-expired jobs. Returns (requeued, dead)."""
    now = datetime.now(tz=UTC)
    rows = (
        session.execute(
            select(TransferJob).where(
                TransferJob.state == "claimed",
                TransferJob.lease_expires_at.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    # Filter in Python so naive-vs-aware comparisons don't explode on SQLite.
    rows = [r for r in rows if (_normalize_tz(r.lease_expires_at) or now) < now]

    requeued = 0
    dead = 0
    for job in rows:
        attempts = job.attempt_count or 0
        if attempts >= max_retries:
            session.execute(
                update(TransferJob)
                .where(TransferJob.transfer_job_pk == job.transfer_job_pk)
                .values(
                    state="dead",
                    lease_owner=None,
                    lease_expires_at=None,
                )
            )
            session.add(
                TransferJobDeadLetter(
                    transfer_job_pk=job.transfer_job_pk,
                    dead_at=now,
                    reason_code="LEASE_REAPED_EXHAUSTED",
                    reason_detail=f"attempts={attempts}",
                    attempts=attempts,
                )
            )
            dead += 1
        else:
            session.execute(
                update(TransferJob)
                .where(TransferJob.transfer_job_pk == job.transfer_job_pk)
                .values(
                    state="queued",
                    lease_owner=None,
                    lease_expires_at=None,
                )
            )
            requeued += 1
    return requeued, dead


__all__ = [
    "complete_job",
    "fail_job",
    "reap_expired_leases",
    "report_progress",
]
