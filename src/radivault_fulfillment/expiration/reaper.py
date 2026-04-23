"""Order expiry ticker (FR-74)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import OrderOutbox
from radivault_fulfillment.orders.repository import find_expired_orders
from radivault_fulfillment.orders.state_machine import transition
from radivault_fulfillment.telemetry import EXPIRED_ORDERS_TOTAL

log = logging.getLogger("radivault_fulfillment.expiration.reaper")


def reap_expired_orders(session: Session, *, limit: int = 100) -> int:
    """Find orders past ``expires_at`` + transition to ``expired``.

    Returns the number of orders transitioned. Safe to run concurrently —
    each ``UPDATE`` is guarded by the FSM's same-state-row-lock predicate.
    """
    rows = find_expired_orders(session, limit=limit)
    n = 0
    for order in rows:
        try:
            transition(
                session,
                order_pk=order.order_pk,
                from_state=order.status,
                to_state="expired",
                actor="timer",
                event="order.expired",
                actor_ref="fulfillment-expiry-ticker",
            )
        except Exception as exc:  # pragma: no cover — defensive
            log.warning(
                "expiry_transition_failed",
                extra={
                    "event": "order.expire.failed",
                    "order_id": order.order_id,
                    "detail": str(exc),
                },
            )
            continue
        session.add(
            OrderOutbox(
                order_pk=order.order_pk,
                event_type="order.expired",
                payload={"order_pk": order.order_pk},
            )
        )
        n += 1
    EXPIRED_ORDERS_TOTAL.inc(n)
    return n


__all__ = ["reap_expired_orders"]
