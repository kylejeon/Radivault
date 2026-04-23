"""Long-poll claim logic for Gateway transfer-jobs (FR-37/38/39/42).

Two paths:

- **Fast path**: an unclaimed row already exists → ``SELECT … FOR UPDATE
  SKIP LOCKED LIMIT 1`` → UPDATE to ``claimed`` in the same TX.
- **Slow path**: no rows in queue → subscribe to Redis channel
  ``transfer_job_hospital:{hospital_pk}`` for up to ``wait`` seconds, then
  re-poll once.

SKIP LOCKED semantics are PostgreSQL-only. On SQLite (tests) we fall back
to a plain SELECT+UPDATE; concurrency tests must mock the Redis pub/sub
path or rely on an integration harness against real PG.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import TransferJob

log = logging.getLogger("radivault_fulfillment.jobs.long_poll")


@dataclass
class ClaimedJob:
    transfer_job: TransferJob
    lease_expires_at: datetime


def _build_select(hospital_pk: int, dialect: str):
    stmt = (
        select(TransferJob)
        .where(TransferJob.state == "queued", TransferJob.hospital_pk == hospital_pk)
        .order_by(TransferJob.created_at.asc())
        .limit(1)
    )
    if dialect == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    return stmt


def try_claim_once(
    session: Session,
    *,
    hospital_pk: int,
    gateway_id: str,
    lease_ttl_seconds: int,
) -> ClaimedJob | None:
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    stmt = _build_select(hospital_pk, dialect)
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        return None

    now = datetime.now(tz=UTC)
    lease_expires_at = now + timedelta(seconds=lease_ttl_seconds)
    upd = (
        update(TransferJob)
        .where(
            TransferJob.transfer_job_pk == row.transfer_job_pk,
            TransferJob.state == "queued",
        )
        .values(
            state="claimed",
            lease_owner=gateway_id,
            lease_expires_at=lease_expires_at,
            claimed_at=now,
            attempt_count=TransferJob.attempt_count + 1,
        )
    )
    res = session.execute(upd)
    if res.rowcount == 0:
        # Another TX raced us (shouldn't happen under SKIP LOCKED but be
        # defensive for SQLite fallback).
        return None

    session.flush()
    session.refresh(row)
    return ClaimedJob(transfer_job=row, lease_expires_at=lease_expires_at)


def claim_with_longpoll(
    session: Session,
    *,
    hospital_pk: int,
    gateway_id: str,
    lease_ttl_seconds: int,
    wait_seconds: int = 30,
    redis_client=None,
    channel_prefix: str = "transfer_job_hospital:",
    sleep_fn=time.sleep,
) -> ClaimedJob | None:
    """Try once, then wait on Redis pub/sub (FR-39), then try once more."""
    claim = try_claim_once(
        session,
        hospital_pk=hospital_pk,
        gateway_id=gateway_id,
        lease_ttl_seconds=lease_ttl_seconds,
    )
    if claim is not None:
        return claim

    if wait_seconds <= 0 or redis_client is None:
        return None

    channel = f"{channel_prefix}{hospital_pk}"
    pubsub = None
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            remaining = max(0.25, deadline - time.monotonic())
            # get_message with timeout returns None when no messages arrive.
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=remaining)
            if msg is not None:
                break
            sleep_fn(0.05)
    except Exception as exc:
        # Fall through to best-effort retry — long-poll should never hard-fail.
        log.warning(
            "long_poll_redis_error",
            extra={"event": "long_poll.redis_error", "detail": str(exc)},
        )
    finally:
        if pubsub is not None:
            try:
                pubsub.unsubscribe()
                pubsub.close()
            except Exception:
                pass

    return try_claim_once(
        session,
        hospital_pk=hospital_pk,
        gateway_id=gateway_id,
        lease_ttl_seconds=lease_ttl_seconds,
    )


__all__ = ["ClaimedJob", "claim_with_longpoll", "try_claim_once"]
