"""Cancellation flow — buyer + admin-force variants (FR-21..FR-24, FR-78)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import (
    Order,
    OrderItem,
    OrderOutbox,
    UnlinkedStudy,
)
from radivault_fulfillment.errors import OrderStateTransition
from radivault_fulfillment.orders.repository import (
    mark_transfer_jobs_cancelled_for_order,
)
from radivault_fulfillment.orders.state_machine import transition

BUYER_ALLOWED_SOURCES: frozenset[str] = frozenset(
    {"draft", "submitted", "validating", "validated", "queued"}
)

ADMIN_ALLOWED_SOURCES: frozenset[str] = BUYER_ALLOWED_SOURCES | {
    "fetching",
    "staging_partial",
    "staging_complete",
    "ready_for_download",
}


def cancel_as_buyer(
    session: Session,
    *,
    order: Order,
    reason: str | None = None,
) -> datetime:
    """Cancel an order from the buyer plane. Returns the cancelled_at timestamp."""
    if order.status not in BUYER_ALLOWED_SOURCES:
        raise OrderStateTransition(
            detail=f"buyer cancel not allowed in state {order.status!r}",
            hint=(
                "admin cancellation required; contact support"
                if order.status in {"fetching", "staging_partial", "staging_complete"}
                else None
            ),
        )
    result = transition(
        session,
        order_pk=order.order_pk,
        from_state=order.status,
        to_state="cancelled",
        actor="buyer",
        event="order.cancelled",
        reason=reason,
        actor_ref=str(order.buyer_pk),
        extra_set={"cancel_requested": True},
    )
    mark_transfer_jobs_cancelled_for_order(session, order_pk=order.order_pk)
    session.add(
        OrderOutbox(
            order_pk=order.order_pk,
            event_type="order.cancelled",
            payload={"order_pk": order.order_pk, "actor": "buyer"},
        )
    )
    return result.at


def cancel_as_admin(
    session: Session,
    *,
    order: Order,
    admin_user: str,
    reason: str,
    detach_unlinked: bool = True,
) -> datetime:
    """Admin cancellation — allowed from fetching/staging_* too (FR-78)."""
    if order.status not in ADMIN_ALLOWED_SOURCES:
        raise OrderStateTransition(detail=f"admin cancel not allowed in state {order.status!r}")
    result = transition(
        session,
        order_pk=order.order_pk,
        from_state=order.status,
        to_state="cancelled",
        actor="admin",
        event="order.cancelled.admin_force",
        reason=reason,
        actor_ref=admin_user,
        extra_set={"cancel_requested": True},
    )
    mark_transfer_jobs_cancelled_for_order(session, order_pk=order.order_pk)

    if detach_unlinked:
        # Any already-staged order_item becomes an unlinked_study (FR-78/79).
        items = (
            session.query(OrderItem)
            .filter(
                OrderItem.order_pk == order.order_pk,
                OrderItem.state.in_(["staged", "hot_hit_staged", "copied"]),
            )
            .all()
        )
        now = datetime.now(tz=UTC)
        for item in items:
            session.add(
                UnlinkedStudy(
                    pseudo_study_uid=item.pseudo_study_uid,
                    hospital_pk=item.hospital_pk,
                    original_order_pk=order.order_pk,
                    detached_at=now,
                    disposition="available_for_reassignment",
                )
            )
            # Mark the item as detached so it won't surface on buyer GETs.
            item.state = "detached"

    session.add(
        OrderOutbox(
            order_pk=order.order_pk,
            event_type="order.cancelled",
            payload={"order_pk": order.order_pk, "actor": "admin"},
        )
    )
    return result.at


__all__ = [
    "ADMIN_ALLOWED_SOURCES",
    "BUYER_ALLOWED_SOURCES",
    "cancel_as_admin",
    "cancel_as_buyer",
]
