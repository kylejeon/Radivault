"""Fan out ``order.queue_transfer_jobs`` outbox events into transfer_job rows.

Called by the outbox poller (FR-31). For the all-hot-hit path we don't emit
transfer_job rows at all — the poller synthesises a direct
``order.staging_complete`` event instead.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session
from ulid import ULID

from radivault_fulfillment.db.models import (
    OrderOutbox,
    TransferJob,
)

log = logging.getLogger("radivault_fulfillment.jobs.dispatcher")


def fan_out_transfer_jobs(
    session: Session,
    *,
    outbox_row: OrderOutbox,
    ruleset_version: str,
    salt_version: int,
) -> list[TransferJob]:
    """Insert one transfer_job per hospital group (FR-32).

    Returns the created rows. If the cohort is all-hot (empty
    ``hospital_groups``), returns an empty list and enqueues a
    ``order.staging_complete`` follow-up event in the outbox.
    """
    payload = outbox_row.payload or {}
    hospital_groups: list[dict] = payload.get("hospital_groups") or []
    order_pk: int = int(payload["order_pk"])
    created: list[TransferJob] = []

    if not hospital_groups:
        # All-hot path — skip transfer_job creation (FR-34).
        session.add(
            OrderOutbox(
                order_pk=order_pk,
                event_type="order.staging_complete",
                payload={"order_pk": order_pk, "path": "hot"},
            )
        )
    else:
        for group in hospital_groups:
            tj = TransferJob(
                transfer_job_id=f"tj_{ULID()!s}",
                order_pk=order_pk,
                hospital_pk=int(group["hospital_pk"]),
                state="queued",
                attempt_count=0,
                studies=group["studies"],
                n_fetched=0,
                n_deided=0,
                n_uploaded=0,
                ruleset_version_required=ruleset_version,
                salt_version_required=salt_version,
            )
            session.add(tj)
            created.append(tj)

    session.execute(
        update(OrderOutbox)
        .where(OrderOutbox.outbox_pk == outbox_row.outbox_pk)
        .values(dispatched_at=datetime.now(tz=UTC))
    )
    log.info(
        "transfer_jobs_fanned_out",
        extra={
            "event": "transfer_job.fanout",
            "order_pk": order_pk,
            "n_jobs": len(created),
        },
    )
    return created


__all__ = ["fan_out_transfer_jobs"]
