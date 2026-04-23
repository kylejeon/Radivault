"""Integration tests for hospital-scoped order stream (D-2 part 2)
and for the buyer_phase field on buyer-facing order responses (D-3).

The hospital bearer comes from the central-ingest ``auth_token`` table that
is already shared with order-fulfillment on the same DB connection in
testing. Auth is resolved by GatewayAuthMiddleware which was extended in
this commit to recognise ``/v1/hospital/*``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from radivault_central.db.models import Hospital
from radivault_fulfillment.db.models import Order, OrderItem

pytestmark = pytest.mark.fulfillment_integration


AGREEMENT = hashlib.sha256(b"MSA v0.1 fulfilment test").hexdigest()


def _auth_hospital(bundle):
    return {"Authorization": f"Bearer {bundle.plaintext}"}


def _auth_buyer(bundle):
    return {"Authorization": f"Bearer {bundle.plaintext}"}


# ---------------------------------------------------------------------------
# Buyer-facing OrderResponse.buyer_phase (D-3)
# ---------------------------------------------------------------------------
def test_buyer_phase_present_on_create(app_client, seeded_studies, seeded_buyer):
    uids = seeded_studies
    _, bundle = seeded_buyer
    r = app_client.post(
        "/v1/orders",
        headers={**_auth_buyer(bundle), "Idempotency-Key": "01HX_BP_IDEM_TEST_001"},
        json={
            "pseudo_study_uids": uids[:2],
            "agreement_hash": AGREEMENT,
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    # Internal state is ``queued`` after create -> buyer_phase is ``accepted``.
    assert body["state"] == "queued"
    assert body["buyer_phase"] == "accepted"


def test_buyer_phase_present_on_list_and_detail(app_client, seeded_studies, seeded_buyer):
    uids = seeded_studies
    _, bundle = seeded_buyer
    create = app_client.post(
        "/v1/orders",
        headers={**_auth_buyer(bundle), "Idempotency-Key": "01HX_BP_IDEM_TEST_002"},
        json={"pseudo_study_uids": uids[:1], "agreement_hash": AGREEMENT},
    )
    assert create.status_code == 202
    order_id = create.json()["order_id"]

    detail = app_client.get(f"/v1/orders/{order_id}", headers=_auth_buyer(bundle))
    assert detail.status_code == 200
    assert "buyer_phase" in detail.json()

    lst = app_client.get("/v1/orders", headers=_auth_buyer(bundle))
    assert lst.status_code == 200
    items = lst.json()["items"]
    assert items
    for it in items:
        assert "buyer_phase" in it


def test_buyer_phase_updates_with_state_change(
    app_client, seeded_studies, seeded_buyer
):
    """Flip the internal status to a 'ready' state and assert the mapping follows."""
    uids = seeded_studies
    _, bundle = seeded_buyer
    create = app_client.post(
        "/v1/orders",
        headers={**_auth_buyer(bundle), "Idempotency-Key": "01HX_BP_IDEM_TEST_003"},
        json={"pseudo_study_uids": uids[:1], "agreement_hash": AGREEMENT},
    )
    assert create.status_code == 202
    order_id = create.json()["order_id"]

    # Directly force the status via the session — bypasses FSM for test
    # expediency; we're testing the serialiser, not the state machine.
    factory = app_client.app.state.session_factory
    with factory() as s:
        order = s.query(Order).filter_by(order_id=order_id).one()
        order.status = "ready_for_download"
        s.commit()

    detail = app_client.get(f"/v1/orders/{order_id}", headers=_auth_buyer(bundle))
    assert detail.status_code == 200
    body = detail.json()
    assert body["state"] == "ready_for_download"
    assert body["buyer_phase"] == "ready_to_download"


# ---------------------------------------------------------------------------
# /v1/hospital/me/orders
# ---------------------------------------------------------------------------
def test_hospital_orders_auth_missing_returns_401(app_client):
    r = app_client.get("/v1/hospital/me/orders")
    assert r.status_code == 401


def test_hospital_orders_returns_envelope_with_masked_id(
    app_client, seeded_studies, seeded_buyer, seeded_hospital
):
    uids = seeded_studies
    _, buyer_bundle = seeded_buyer
    _hospital, hosp_bundle = seeded_hospital

    # Create an order so there's something to enumerate.
    create = app_client.post(
        "/v1/orders",
        headers={**_auth_buyer(buyer_bundle), "Idempotency-Key": "01HX_HO_IDEM_TEST_001"},
        json={"pseudo_study_uids": uids[:3], "agreement_hash": AGREEMENT},
    )
    assert create.status_code == 202
    order_id = create.json()["order_id"]

    r = app_client.get("/v1/hospital/me/orders", headers=_auth_hospital(hosp_bundle))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert data["hospital_id"] == "hosp_abc"
    assert len(data["orders"]) >= 1
    o = data["orders"][0]
    # Mask format: ord_<4-8 chars>
    assert o["order_id_masked"].startswith("ord_")
    assert len(o["order_id_masked"]) <= 12
    # Full order_id must NOT appear.
    assert order_id not in r.text
    # phase is a buyer_phase string.
    assert o["phase"] in {
        "accepted",
        "fetching_from_hospital",
        "preparing_download",
        "ready_to_download",
        "completed",
        "cancelled",
        "expired",
        "failed",
    }


def test_hospital_orders_limits_to_request(
    app_client, seeded_studies, seeded_buyer, seeded_hospital
):
    uids = seeded_studies
    _, buyer_bundle = seeded_buyer
    _, hosp_bundle = seeded_hospital

    # Seed 4 orders for the hospital. Each must use a distinct cohort row
    # and the tier quota is limited — we go direct to the DB to avoid
    # validator quota gymnastics while still exercising the SELECT path.
    factory = app_client.app.state.session_factory
    with factory() as s:
        hospital = s.query(Hospital).filter_by(hospital_id="hosp_abc").one()
        buyer_pk = 1  # seeded_buyer fixture always seeds buyer_pk=1 on sqlite
        for i in range(4):
            o = Order(
                order_id=f"ord_seed_{i:05d}",
                buyer_pk=buyer_pk,
                kid="rv_live_seed",
                status="queued",
                status_billing="pending_billing",
                n_studies=1,
                total_bytes=1024,
                total_estimated_usd=5,
                tier="preview",
                agreement_hash=AGREEMENT,
                submitted_at=datetime.now(tz=UTC) - timedelta(minutes=i),
            )
            s.add(o)
            s.flush()
            s.add(
                OrderItem(
                    order_pk=o.order_pk,
                    pseudo_study_uid=uids[0],
                    hospital_pk=hospital.hospital_pk,
                    source="on_demand",
                    state="pending",
                )
            )
        s.commit()

    r = app_client.get(
        "/v1/hospital/me/orders?limit=2", headers=_auth_hospital(hosp_bundle)
    )
    assert r.status_code == 200
    assert len(r.json()["data"]["orders"]) == 2


def test_hospital_orders_does_not_leak_buyer_identity(
    app_client, seeded_studies, seeded_buyer, seeded_hospital
):
    """Response body must not include buyer_id / buyer_pk / kid."""
    uids = seeded_studies
    _, buyer_bundle = seeded_buyer
    _, hosp_bundle = seeded_hospital
    app_client.post(
        "/v1/orders",
        headers={**_auth_buyer(buyer_bundle), "Idempotency-Key": "01HX_HO_IDEM_TEST_009"},
        json={"pseudo_study_uids": uids[:1], "agreement_hash": AGREEMENT},
    )
    r = app_client.get("/v1/hospital/me/orders", headers=_auth_hospital(hosp_bundle))
    text = r.text
    for forbidden in ("buy_test_001", "buyer_pk", "kid", "rv_live"):
        assert forbidden not in text


def test_hospital_orders_scope_isolation_between_hospitals(
    app_client, seeded_studies, seeded_buyer, seeded_hospital
):
    """Two hospitals — only each sees orders containing their own study."""
    from radivault_central.auth.tokens import generate_token
    from radivault_central.db.models import AuthToken, Hospital, Study

    uids = seeded_studies
    _, buyer_bundle = seeded_buyer
    _, hosp_bundle = seeded_hospital

    factory = app_client.app.state.session_factory
    # Add a second hospital with no order history.
    with factory() as s:
        other = Hospital(
            hospital_id="hosp_other_iso",
            name="Other ISO",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
        )
        s.add(other)
        s.flush()
        other_bundle = generate_token()
        s.add(
            AuthToken(
                hospital_pk=other.hospital_pk,
                token_kid=other_bundle.kid,
                token_hash=other_bundle.hash,
            )
        )
        # Add a study owned by 'other' to prove it isn't leaked to hosp_abc.
        other_uid = "2.25.test.other.001"
        s.add(
            Study(
                pseudo_study_uid=other_uid,
                hospital_pk=other.hospital_pk,
                modality="CT",
                n_instances=1,
                n_series=1,
                total_bytes=1024,
                central_job_id="ingest_other",
                gateway_id="gw_other",
                ingested_at=datetime.now(tz=UTC),
            )
        )
        s.commit()

    # Submit an order against the original hospital's studies.
    app_client.post(
        "/v1/orders",
        headers={**_auth_buyer(buyer_bundle), "Idempotency-Key": "01HX_HO_IDEM_TEST_X01"},
        json={"pseudo_study_uids": uids[:1], "agreement_hash": AGREEMENT},
    )

    r_a = app_client.get("/v1/hospital/me/orders", headers=_auth_hospital(hosp_bundle))
    r_b = app_client.get(
        "/v1/hospital/me/orders",
        headers={"Authorization": f"Bearer {other_bundle.plaintext}"},
    )

    # hosp_abc sees at least one order, hosp_other_iso sees zero.
    assert r_a.status_code == 200
    assert r_b.status_code == 200
    assert len(r_a.json()["data"]["orders"]) >= 1
    assert r_b.json()["data"]["orders"] == []
