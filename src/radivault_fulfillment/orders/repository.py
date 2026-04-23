"""Data-access helpers for the order FSM + sibling tables."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import (
    Order,
    OrderItem,
    OrderStateHistory,
    TransferJob,
    TransferJobDeadLetter,
)


def get_order_by_id(session: Session, *, order_id: str) -> Order | None:
    return session.execute(select(Order).where(Order.order_id == order_id)).scalar_one_or_none()


def get_order_for_buyer(session: Session, *, order_id: str, buyer_pk: int) -> Order | None:
    """Return the row only if it belongs to ``buyer_pk`` (else None)."""
    return session.execute(
        select(Order).where(Order.order_id == order_id, Order.buyer_pk == buyer_pk)
    ).scalar_one_or_none()


def list_orders_for_buyer(
    session: Session,
    *,
    buyer_pk: int,
    status: list[str] | None = None,
    limit: int = 50,
    before_submitted_at: datetime | None = None,
    before_pk: int | None = None,
) -> list[Order]:
    stmt = select(Order).where(Order.buyer_pk == buyer_pk)
    if status:
        stmt = stmt.where(Order.status.in_(status))
    if before_submitted_at is not None and before_pk is not None:
        stmt = stmt.where(
            and_(
                Order.submitted_at <= before_submitted_at,
                Order.order_pk < before_pk,
            )
        )
    stmt = stmt.order_by(Order.submitted_at.desc(), Order.order_pk.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def list_items_for_order(session: Session, *, order_pk: int) -> list[OrderItem]:
    return list(
        session.execute(select(OrderItem).where(OrderItem.order_pk == order_pk)).scalars().all()
    )


def list_jobs_for_order(session: Session, *, order_pk: int) -> list[TransferJob]:
    return list(
        session.execute(select(TransferJob).where(TransferJob.order_pk == order_pk)).scalars().all()
    )


def list_dlq(session: Session, *, limit: int = 50) -> list[TransferJobDeadLetter]:
    return list(
        session.execute(
            select(TransferJobDeadLetter)
            .where(TransferJobDeadLetter.resolved_at.is_(None))
            .order_by(TransferJobDeadLetter.dead_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def count_orders_by_buyer_since(session: Session, *, buyer_pk: int, since: datetime) -> int:
    return int(
        session.scalar(
            select(func.count(Order.order_pk)).where(
                Order.buyer_pk == buyer_pk,
                Order.submitted_at >= since,
            )
        )
        or 0
    )


def mark_transfer_jobs_cancelled_for_order(session: Session, *, order_pk: int) -> tuple[int, int]:
    """FR-23 cancel cascade.

    - queued → cancelled (hard).
    - claimed → cancel_requested=True (cooperative; Gateway reads the flag
      on next progress ping).

    Returns ``(n_hard_cancelled, n_cooperative)``.
    """
    hard = session.execute(
        update(TransferJob)
        .where(
            TransferJob.order_pk == order_pk,
            TransferJob.state == "queued",
        )
        .values(state="cancelled")
    ).rowcount
    coop = session.execute(
        update(TransferJob)
        .where(
            TransferJob.order_pk == order_pk,
            TransferJob.state == "claimed",
        )
        .values(cancel_requested=True)
    ).rowcount
    return int(hard or 0), int(coop or 0)


def find_expired_orders(session: Session, *, limit: int = 100) -> list[Order]:
    now = datetime.now(tz=UTC)
    rows = list(
        session.execute(
            select(Order)
            .where(
                Order.status.in_(["ready_for_download", "delivering"]),
                Order.expires_at.is_not(None),
            )
            .order_by(Order.expires_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    # SQLite strips tzinfo — coerce to UTC before comparison so the predicate
    # doesn't explode with offset-naive vs offset-aware errors.
    def _coerce(ts):
        return ts.replace(tzinfo=UTC) if (ts is not None and ts.tzinfo is None) else ts

    return [r for r in rows if (_coerce(r.expires_at) or now) < now]


__all__ = [
    "OrderStateHistory",
    "count_orders_by_buyer_since",
    "find_expired_orders",
    "get_order_by_id",
    "get_order_for_buyer",
    "list_dlq",
    "list_items_for_order",
    "list_jobs_for_order",
    "list_orders_for_buyer",
    "mark_transfer_jobs_cancelled_for_order",
    "timedelta",
]


# Export timedelta/datetime for tests/CLI convenience
_ = timedelta
