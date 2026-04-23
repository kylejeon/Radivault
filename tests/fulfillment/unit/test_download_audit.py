"""download_event audit rows (FR-65/69)."""

from __future__ import annotations

from decimal import Decimal

from radivault_fulfillment.db.models import DownloadEvent, Order
from radivault_fulfillment.download.audit import record_url_minted


def _make_order(session):
    from radivault_search.db.models import Buyer

    buyer = Buyer(buyer_id="b_audit", name="b", contact_email="x", tier="preview", scope_json={})
    session.add(buyer)
    session.flush()
    order = Order(
        order_id="ord_audit_01",
        buyer_pk=buyer.buyer_pk,
        kid="kk" * 4,
        status="ready_for_download",
        n_studies=1,
        total_bytes=1024,
        total_estimated_usd=Decimal("5.00"),
        tier="preview",
        agreement_hash="0" * 64,
    )
    session.add(order)
    session.flush()
    return buyer, order


def test_record_url_minted_inserts_row(engine_and_factory):
    _, factory = engine_and_factory
    with factory() as s:
        buyer, order = _make_order(s)
        record_url_minted(
            s,
            order_pk=order.order_pk,
            order_item_pk=None,
            buyer_pk=buyer.buyer_pk,
            kid=order.kid,
            src_ip="203.0.113.5",
            user_agent="pytest/1.0",
            request_id="req_abc",
            object_key="staging/ord/.../x.dcm",
            signature_hash="abcdef0123456789",
            ttl_seconds=86400,
        )
        s.commit()
        events = s.query(DownloadEvent).all()
    assert len(events) == 1
    e = events[0]
    assert e.event_type == "url_minted"
    assert e.signature_hash == "abcdef0123456789"
    assert e.ttl_seconds == 86400
    assert e.request_id == "req_abc"
