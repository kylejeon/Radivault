"""Order FSM — 12 states + 4 terminal (dev-spec §4.5, §8.5).

Transitions use a single source-of-truth matrix and an idempotent DB helper
that performs ``UPDATE order SET status=:to WHERE order_pk=:pk AND
status=:from``. Rowcount=0 ⇒ ``ERR_ORDER_STATE_TRANSITION`` (another TX
either raced us or the transition is illegal).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import Order, OrderStateHistory
from radivault_fulfillment.errors import OrderStateTransition

# Canonical state set.
STATES: frozenset[str] = frozenset(
    {
        "draft",
        "submitted",
        "validating",
        "validated",
        "queued",
        "fetching",
        "staging_partial",
        "staging_complete",
        "ready_for_download",
        "delivering",
        "delivered",
        "expired",
        "cancelled",
        "failed",
    }
)

TERMINAL: frozenset[str] = frozenset({"delivered", "expired", "cancelled", "failed"})

# from -> {to -> {actors}} — the rulebook.
TRANSITIONS: dict[str, dict[str, frozenset[str]]] = {
    "draft": {"submitted": frozenset({"buyer"})},
    "submitted": {"validating": frozenset({"system"})},
    "validating": {
        "validated": frozenset({"system"}),
        "failed": frozenset({"system"}),
    },
    "validated": {"queued": frozenset({"system"})},
    "queued": {
        "fetching": frozenset({"gateway"}),
        "cancelled": frozenset({"buyer", "admin"}),
        "staging_complete": frozenset({"system"}),  # all-hot path
    },
    "fetching": {
        "staging_partial": frozenset({"gateway"}),
        "staging_complete": frozenset({"gateway"}),
        "cancelled": frozenset({"admin"}),
        "failed": frozenset({"system"}),
    },
    "staging_partial": {
        "staging_complete": frozenset({"gateway"}),
        "cancelled": frozenset({"admin"}),
        "failed": frozenset({"system"}),
    },
    "staging_complete": {
        "ready_for_download": frozenset({"system"}),
        "cancelled": frozenset({"admin"}),
    },
    "ready_for_download": {
        "delivering": frozenset({"system"}),
        "expired": frozenset({"timer"}),
        "cancelled": frozenset({"admin"}),
    },
    "delivering": {
        "delivered": frozenset({"system"}),
        "expired": frozenset({"timer"}),
    },
}


def is_allowed(from_state: str, to_state: str, actor: str) -> bool:
    if from_state in TERMINAL:
        return False
    allowed = TRANSITIONS.get(from_state, {}).get(to_state)
    return allowed is not None and actor in allowed


@dataclass
class TransitionResult:
    order_pk: int
    from_state: str
    to_state: str
    actor: str
    at: datetime
    extra: dict = field(default_factory=dict)


def transition(
    session: Session,
    *,
    order_pk: int,
    from_state: str,
    to_state: str,
    actor: str,
    event: str,
    reason: str | None = None,
    actor_ref: str | None = None,
    extra_set: dict | None = None,
) -> TransitionResult:
    """Atomically transition an order and append a history row.

    Raises :class:`OrderStateTransition` if the transition isn't allowed or
    another TX has already moved the row.
    """
    if not is_allowed(from_state, to_state, actor):
        raise OrderStateTransition(
            detail=f"transition {from_state} -> {to_state} not allowed for {actor}"
        )
    now = datetime.now(tz=UTC)
    values: dict = {"status": to_state}
    values.update(extra_set or {})
    # Timestamp fields auto-populated on well-known transitions.
    stamp_field_map = {
        "validated": "validated_at",
        "queued": "queued_at",
        "staging_complete": "staging_complete_at",
        "ready_for_download": "ready_at",
        "cancelled": "cancelled_at",
        "expired": "expired_at",
        "delivered": "delivered_at",
        "failed": "failed_at",
    }
    if (ts_field := stamp_field_map.get(to_state)) and ts_field not in values:
        values[ts_field] = now

    stmt = (
        update(Order)
        .where(Order.order_pk == order_pk, Order.status == from_state)
        .values(**values)
    )
    result = session.execute(stmt)
    if result.rowcount == 0:
        raise OrderStateTransition(
            detail=f"order {order_pk} not in state {from_state!r}"
        )

    session.add(
        OrderStateHistory(
            order_pk=order_pk,
            from_state=from_state,
            to_state=to_state,
            event=event,
            actor=actor,
            actor_ref=actor_ref,
            reason=reason,
            at=now,
        )
    )
    return TransitionResult(
        order_pk=order_pk,
        from_state=from_state,
        to_state=to_state,
        actor=actor,
        at=now,
        extra=values,
    )


__all__ = [
    "STATES",
    "TERMINAL",
    "TRANSITIONS",
    "TransitionResult",
    "is_allowed",
    "transition",
]
