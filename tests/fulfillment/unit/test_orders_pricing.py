"""Pricing stub (FR-15) + order-creation state/row counts."""

from __future__ import annotations

from decimal import Decimal

from radivault_fulfillment.config import TierDefaults
from radivault_fulfillment.db.models import (
    Order,
    OrderItem,
    OrderOutbox,
    OrderStateHistory,
)
from radivault_fulfillment.orders.pricing import estimate_order_price
from radivault_fulfillment.orders.service import create_order
from radivault_fulfillment.orders.validator import validate_order


def test_estimate_order_price_linear():
    tier = TierDefaults(unit_price_usd=5.0)
    assert estimate_order_price(tier, n_studies=0) == Decimal("0.00")
    assert estimate_order_price(tier, n_studies=10) == Decimal("50.00")


def test_create_order_persists_rows(engine_and_factory, seeded_studies, seeded_buyer, settings):
    _, factory = engine_and_factory
    uids = seeded_studies
    buyer, _ = seeded_buyer
    with factory() as s:
        cohort = validate_order(
            s,
            buyer_pk=buyer.buyer_pk,
            tier=buyer.tier,
            scope_json={},
            tier_cfg=settings.order.tier_preview,
            pseudo_study_uids=uids[:2],
        )
        order, items = create_order(
            s,
            buyer_pk=buyer.buyer_pk,
            kid="kidkidk1",
            tier=buyer.tier,
            tier_cfg=settings.order.tier_preview,
            cohort=cohort,
            agreement_hash="a" * 64,
            notes="test",
            settings=settings,
        )
        s.commit()
    with factory() as s:
        stored = s.query(Order).filter_by(order_id=order.order_id).one()
        items_rows = s.query(OrderItem).filter_by(order_pk=stored.order_pk).all()
        history = s.query(OrderStateHistory).filter_by(order_pk=stored.order_pk).all()
        outbox = s.query(OrderOutbox).filter_by(order_pk=stored.order_pk).all()
    assert stored.status == "queued"
    assert stored.status_billing == "pending_billing"
    assert stored.path_type == "cold"
    assert len(items_rows) == 2
    assert any(h.to_state == "queued" for h in history)
    assert any(e.event_type == "order.queue_transfer_jobs" for e in outbox)
    assert stored.total_estimated_usd == Decimal("10.00")
