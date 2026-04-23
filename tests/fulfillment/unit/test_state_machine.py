"""Order FSM — allowed transitions, terminal protection, history rows."""

from __future__ import annotations

from decimal import Decimal

import pytest

from radivault_fulfillment.db.models import Order, OrderStateHistory
from radivault_fulfillment.errors import OrderStateTransition
from radivault_fulfillment.orders.state_machine import (
    TERMINAL,
    is_allowed,
    transition,
)


def _make_order(session, **overrides) -> Order:
    # Minimal seed — a buyer + order row.
    from radivault_search.db.models import Buyer

    buyer = Buyer(
        buyer_id="b_fsm",
        name="FSM buyer",
        contact_email="x@y",
        tier="preview",
        scope_json={},
    )
    session.add(buyer)
    session.flush()
    order = Order(
        order_id="ord_fsm_01",
        buyer_pk=buyer.buyer_pk,
        kid="kidkid01",
        status=overrides.get("status", "queued"),
        n_studies=1,
        total_bytes=1024,
        total_estimated_usd=Decimal("5.00"),
        tier="preview",
        agreement_hash="0" * 64,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def test_is_allowed_matrix() -> None:
    assert is_allowed("queued", "fetching", "gateway") is True
    assert is_allowed("queued", "cancelled", "buyer") is True
    # Buyer cannot force fetching -> cancelled.
    assert is_allowed("fetching", "cancelled", "buyer") is False
    # Admin can.
    assert is_allowed("fetching", "cancelled", "admin") is True
    # Terminal states never allow anything.
    for t in TERMINAL:
        assert is_allowed(t, "queued", "system") is False


def test_transition_happy_path(engine_and_factory) -> None:
    _, factory = engine_and_factory
    with factory() as session:
        order = _make_order(session, status="queued")

        result = transition(
            session,
            order_pk=order.order_pk,
            from_state="queued",
            to_state="fetching",
            actor="gateway",
            event="transfer_job.claimed",
        )
        session.commit()
        session.refresh(order)

        assert order.status == "fetching"
        assert result.to_state == "fetching"
        hist = session.query(OrderStateHistory).filter_by(order_pk=order.order_pk).all()
        assert any(h.from_state == "queued" and h.to_state == "fetching" for h in hist)


def test_transition_rejects_illegal(engine_and_factory) -> None:
    _, factory = engine_and_factory
    with factory() as session:
        order = _make_order(session, status="queued")
        with pytest.raises(OrderStateTransition):
            transition(
                session,
                order_pk=order.order_pk,
                from_state="queued",
                to_state="delivered",  # skip-jumping the FSM
                actor="buyer",
                event="bogus",
            )


def test_transition_rejects_when_row_already_moved(engine_and_factory) -> None:
    _, factory = engine_and_factory
    with factory() as session:
        order = _make_order(session, status="queued")
        # First transition succeeds...
        transition(
            session,
            order_pk=order.order_pk,
            from_state="queued",
            to_state="fetching",
            actor="gateway",
            event="claim",
        )
        session.commit()
        # ...but now pretending from_state is still queued fails (row-lock pattern).
        with pytest.raises(OrderStateTransition):
            transition(
                session,
                order_pk=order.order_pk,
                from_state="queued",
                to_state="cancelled",
                actor="buyer",
                event="cancel",
            )
