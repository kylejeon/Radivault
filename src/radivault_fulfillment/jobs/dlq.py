"""Dead-letter queue helpers (FR-55)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import TransferJob, TransferJobDeadLetter


def count_unresolved(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count(TransferJobDeadLetter.dlq_pk)).where(
                TransferJobDeadLetter.resolved_at.is_(None)
            )
        )
        or 0
    )


def resolve(
    session: Session,
    *,
    dlq_pk: int,
    resolved_by: str,
    resolution: str,
) -> TransferJobDeadLetter:
    row = session.get(TransferJobDeadLetter, dlq_pk)
    if row is None:
        raise LookupError(f"dlq_pk={dlq_pk} not found")
    row.resolved_at = datetime.now(tz=UTC)
    row.resolved_by = resolved_by
    row.resolution = resolution
    return row


def requeue_from_dlq(
    session: Session,
    *,
    transfer_job_id: str,
    resolved_by: str,
    reset_attempts: bool = True,
) -> TransferJob:
    job = session.execute(
        select(TransferJob).where(TransferJob.transfer_job_id == transfer_job_id)
    ).scalar_one_or_none()
    if job is None:
        raise LookupError(f"transfer_job_id={transfer_job_id} not found")
    if job.state != "dead":
        raise ValueError(f"job state must be 'dead' (got {job.state!r})")
    session.execute(
        update(TransferJob)
        .where(TransferJob.transfer_job_pk == job.transfer_job_pk)
        .values(
            state="queued",
            lease_owner=None,
            lease_expires_at=None,
            attempt_count=0 if reset_attempts else job.attempt_count,
        )
    )
    # Mark any open DLQ row for this job as resolved.
    session.execute(
        update(TransferJobDeadLetter)
        .where(
            TransferJobDeadLetter.transfer_job_pk == job.transfer_job_pk,
            TransferJobDeadLetter.resolved_at.is_(None),
        )
        .values(
            resolved_at=datetime.now(tz=UTC),
            resolved_by=resolved_by,
            resolution="requeued",
        )
    )
    session.refresh(job)
    return job


__all__ = ["count_unresolved", "requeue_from_dlq", "resolve"]
