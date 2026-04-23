"""Buyer + admin cancellation (FR-21..24, FR-78)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from radivault_fulfillment.cancellation.service import (
    cancel_as_admin,
    cancel_as_buyer,
)
from radivault_fulfillment.db.models import (
    Order,
    OrderItem,
    TransferJob,
    UnlinkedStudy,
)
from radivault_fulfillment.errors import OrderStateTransition


def _seed_order(session, *, status: str, hospital_pk: int) -> Order:
    from radivault_search.db.models import Buyer

    buyer = Buyer(
        buyer_id=f"b_cnx_{status}",
        name="b",
        contact_email="x",
        tier="preview",
        scope_json={},
    )
    session.add(buyer)
    session.flush()
    order = Order(
        order_id=f"ord_cnx_{status}",
        buyer_pk=buyer.buyer_pk,
        kid="kk" * 4,
        status=status,
        n_studies=1,
        total_bytes=1024,
        total_estimated_usd=Decimal("5.00"),
        tier="preview",
        agreement_hash="0" * 64,
    )
    session.add(order)
    session.flush()
    item = OrderItem(
        order_pk=order.order_pk,
        pseudo_study_uid=f"2.25.cnx.{status}",
        hospital_pk=hospital_pk,
        source="on_demand",
        state="staged" if status != "queued" else "pending",
        n_instances=1,
        total_bytes=1024,
    )
    session.add(item)
    session.add(
        TransferJob(
            transfer_job_id=f"tj_cnx_{status}",
            order_pk=order.order_pk,
            hospital_pk=hospital_pk,
            state="queued" if status == "queued" else "claimed",
            attempt_count=0,
            studies=[{"pseudo_study_uid": item.pseudo_study_uid, "expected_instances": 1}],
            ruleset_version_required="v0.1.0",
            salt_version_required=1,
        )
    )
    session.commit()
    session.refresh(order)
    return order


def test_buyer_cancel_from_queued(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        order = _seed_order(s, status="queued", hospital_pk=hosp.hospital_pk)
        cancel_as_buyer(s, order=order, reason="test")
        s.commit()
    with factory() as s:
        order = s.query(Order).filter_by(order_id="ord_cnx_queued").one()
        jobs = s.query(TransferJob).filter_by(order_pk=order.order_pk).all()
    assert order.status == "cancelled"
    assert order.cancel_requested is True
    assert all(j.state == "cancelled" for j in jobs)


def test_buyer_cancel_from_fetching_rejected(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        order = _seed_order(s, status="fetching", hospital_pk=hosp.hospital_pk)
        with pytest.raises(OrderStateTransition) as exc:
            cancel_as_buyer(s, order=order)
    assert exc.value.code == "ERR_ORDER_STATE_TRANSITION"


def test_admin_force_cancel_detaches_staged_items(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        order = _seed_order(s, status="fetching", hospital_pk=hosp.hospital_pk)
        cancel_as_admin(s, order=order, admin_user="admin_kyle", reason="ops")
        s.commit()
    with factory() as s:
        order = s.query(Order).filter_by(order_id="ord_cnx_fetching").one()
        items = s.query(OrderItem).filter_by(order_pk=order.order_pk).all()
        unlinked = s.query(UnlinkedStudy).filter_by(original_order_pk=order.order_pk).all()
        jobs = s.query(TransferJob).filter_by(order_pk=order.order_pk).all()
    assert order.status == "cancelled"
    assert len(unlinked) == 1
    assert unlinked[0].disposition == "available_for_reassignment"
    # Items detached so buyer GET won't surface them.
    assert all(it.state == "detached" for it in items)
    # claim job received cooperative cancel flag.
    assert all(j.cancel_requested for j in jobs if j.state == "claimed")
