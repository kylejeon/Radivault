"""End-to-end flow via TestClient — buyer creates order, gateway claims,
progresses, completes; buyer mints download URLs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.fulfillment_integration

# Allowed to run in-process (no external services needed).


def _auth(bundle):
    return {"Authorization": f"Bearer {bundle.plaintext}"}


def test_full_order_flow(app_client, seeded_studies, seeded_buyer, seeded_hospital):
    """Buyer → order → gateway claim → progress → complete → URL mint."""
    import hashlib

    AGREEMENT = hashlib.sha256(b"MSA v0.1 fulfilment test").hexdigest()
    uids = seeded_studies
    buyer, bundle = seeded_buyer
    hosp, hosp_bundle = seeded_hospital

    # 1. Create order.
    r = app_client.post(
        "/v1/orders",
        headers={
            **_auth(bundle),
            "Idempotency-Key": "01HX_TEST_ORDER_IDEM_01",
        },
        json={
            "pseudo_study_uids": uids[:2],
            "agreement_hash": AGREEMENT,
            "notes": "e2e",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    order_id = body["order_id"]
    assert body["state"] == "queued"
    assert body["n_studies"] == 2
    assert body["total_estimated_usd"] == 10.0
    assert body["path_type"] == "cold"

    # 2. Replay same Idempotency-Key.
    r2 = app_client.post(
        "/v1/orders",
        headers={
            **_auth(bundle),
            "Idempotency-Key": "01HX_TEST_ORDER_IDEM_01",
        },
        json={
            "pseudo_study_uids": uids[:2],
            "agreement_hash": AGREEMENT,
        },
    )
    assert r2.status_code == 202
    assert r2.headers.get("Idempotency-Replayed") == "true"
    assert r2.json()["order_id"] == order_id

    # 3. Fan-out transfer_jobs manually (outbox poller isn't running).
    from radivault_fulfillment.db.models import Order, OrderOutbox
    from radivault_fulfillment.jobs.dispatcher import fan_out_transfer_jobs

    factory = app_client.app.state.session_factory
    with factory() as s:
        order_pk = s.query(Order).filter_by(order_id=order_id).one().order_pk
        undispatched = (
            s.query(OrderOutbox)
            .filter(OrderOutbox.order_pk == order_pk, OrderOutbox.dispatched_at.is_(None))
            .all()
        )
        for ob in undispatched:
            if ob.event_type == "order.queue_transfer_jobs":
                fan_out_transfer_jobs(s, outbox_row=ob, ruleset_version="v0.1.0", salt_version=1)
        s.commit()

    # 4. Gateway claims the job (use hospital auth_token).
    r = app_client.get(
        "/v1/gateway/transfer-jobs?wait=0",
        headers={"Authorization": f"Bearer {hosp_bundle.plaintext}"},
    )
    assert r.status_code == 200, r.text
    claim = r.json()
    assert claim["hospital_id"] == hosp.hospital_id
    tj_id = claim["transfer_job_id"]

    # 5. Progress report.
    r = app_client.post(
        f"/v1/gateway/transfer-jobs/{tj_id}/progress",
        headers={
            "Authorization": f"Bearer {hosp_bundle.plaintext}",
            "Idempotency-Key": "01HX_TEST_PROGRESS_01",
        },
        json={"n_fetched": 2, "n_deided": 2, "n_uploaded": 2, "lease_extend": True},
    )
    assert r.status_code == 200
    assert r.json()["cancel_requested"] is False

    # 6. Complete the job.
    r = app_client.post(
        f"/v1/gateway/transfer-jobs/{tj_id}/complete",
        headers={
            "Authorization": f"Bearer {hosp_bundle.plaintext}",
            "Idempotency-Key": "01HX_TEST_COMPLETE_01",
        },
        json={
            "manifest": [
                {
                    "pseudo_study_uid": uid,
                    "n_instances": 2,
                    "total_bytes": 512 * 1024,
                    "status": "uploaded",
                    "central_job_ids": [f"ingest_{uid}"],
                }
                for uid in uids[:2]
            ],
            "audit_ref": {"seq": 1, "hash": "sha256:abc"},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "completed"
    assert r.json()["order_state"] == "staging_complete"

    # 7. Simulate ready_for_download transition (the outbox-driven
    # staging_copy step is an operator job; v0.1 reaper-ish path is
    # synthesised here for the test).
    from radivault_fulfillment.orders.state_machine import transition

    with factory() as s:
        order = s.query(Order).filter_by(order_id=order_id).one()
        transition(
            s,
            order_pk=order.order_pk,
            from_state="staging_complete",
            to_state="ready_for_download",
            actor="system",
            event="order.staging_copy_complete",
        )
        order.expires_at = datetime.now(tz=UTC) + timedelta(days=7)
        s.commit()

    # 8. Mint download URLs.
    r = app_client.post(
        f"/v1/orders/{order_id}/download-urls",
        headers=_auth(bundle),
        json={"ttl_seconds": 3600},
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    assert batch["order_id"] == order_id
    assert len(batch["items"]) == 2
    assert all("X-Amz-Signature=" in f["url"] for it in batch["items"] for f in it["files"])


def test_cancel_on_queued_order(app_client, seeded_studies, seeded_buyer):
    import hashlib

    AGREEMENT = hashlib.sha256(b"MSA v0.1 fulfilment test").hexdigest()
    uids = seeded_studies
    buyer, bundle = seeded_buyer

    r = app_client.post(
        "/v1/orders",
        headers={**_auth(bundle), "Idempotency-Key": "01HX_CANCEL_IDEM_01"},
        json={"pseudo_study_uids": uids[:1], "agreement_hash": AGREEMENT},
    )
    assert r.status_code == 202
    order_id = r.json()["order_id"]

    r = app_client.post(
        f"/v1/orders/{order_id}/cancel",
        headers={**_auth(bundle), "Idempotency-Key": "01HX_CANCEL_CANCEL_01"},
        json={"reason": "changed mind"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "cancelled"

    # GET should reflect it.
    r = app_client.get(f"/v1/orders/{order_id}", headers=_auth(bundle))
    assert r.status_code == 200
    assert r.json()["state"] == "cancelled"
