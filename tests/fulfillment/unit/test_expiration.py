"""Order expiry ticker (FR-73/74/75)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from radivault_fulfillment.db.models import Order, OrderOutbox
from radivault_fulfillment.expiration.reaper import reap_expired_orders


def _ready_order(session, *, expires_delta_seconds: int, order_id: str = "ord_expiry_1"):
    from radivault_search.db.models import Buyer

    buyer = Buyer(
        buyer_id=f"b_{order_id}",
        name="b",
        contact_email="x",
        tier="preview",
        scope_json={},
    )
    session.add(buyer)
    session.flush()
    now = datetime.now(tz=UTC)
    o = Order(
        order_id=order_id,
        buyer_pk=buyer.buyer_pk,
        kid="kk" * 4,
        status="ready_for_download",
        n_studies=1,
        total_bytes=1024,
        total_estimated_usd=Decimal("5.00"),
        tier="preview",
        agreement_hash="0" * 64,
        submitted_at=now - timedelta(hours=1),
        ready_at=now - timedelta(minutes=30),
        expires_at=now + timedelta(seconds=expires_delta_seconds),
    )
    session.add(o)
    session.commit()
    session.refresh(o)
    return o


def test_reap_picks_up_expired(engine_and_factory):
    _, factory = engine_and_factory
    with factory() as s:
        _ready_order(s, expires_delta_seconds=-60, order_id="ord_exp_old")
        _ready_order(s, expires_delta_seconds=3600, order_id="ord_exp_fresh")
    with factory() as s:
        n = reap_expired_orders(s, limit=10)
        s.commit()
    assert n == 1
    with factory() as s:
        old = s.query(Order).filter_by(order_id="ord_exp_old").one()
        fresh = s.query(Order).filter_by(order_id="ord_exp_fresh").one()
        events = s.query(OrderOutbox).filter_by(order_pk=old.order_pk).all()
    assert old.status == "expired"
    assert old.expired_at is not None
    assert fresh.status == "ready_for_download"
    assert any(e.event_type == "order.expired" for e in events)
