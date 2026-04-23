"""Long-poll claim logic — SKIP LOCKED semantics (SQLite fallback)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from radivault_fulfillment.db.models import Order, TransferJob
from radivault_fulfillment.jobs.long_poll import try_claim_once


def _seed_job(session, *, hospital_pk: int, tj_id: str = "tj_seed") -> TransferJob:
    buyer_pk = _insert_buyer(session)
    order = Order(
        order_id=f"ord_{tj_id}",
        buyer_pk=buyer_pk,
        kid="kid00001",
        status="queued",
        n_studies=1,
        total_bytes=1024,
        total_estimated_usd=Decimal("5.00"),
        tier="preview",
        agreement_hash="0" * 64,
    )
    session.add(order)
    session.flush()
    job = TransferJob(
        transfer_job_id=tj_id,
        order_pk=order.order_pk,
        hospital_pk=hospital_pk,
        state="queued",
        studies=[{"pseudo_study_uid": "2.25.x", "expected_instances": 1}],
        ruleset_version_required="v0.1.0",
        salt_version_required=1,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _insert_buyer(session) -> int:
    from radivault_search.db.models import Buyer

    buyer = Buyer(
        buyer_id=f"b_lp_{int(datetime.now(tz=UTC).timestamp() * 1000)}",
        name="lp buyer",
        contact_email="x@y",
        tier="preview",
        scope_json={},
    )
    session.add(buyer)
    session.flush()
    return buyer.buyer_pk


def test_claim_sets_state_and_lease(engine_and_factory, seeded_hospital) -> None:
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_job(s, hospital_pk=hosp.hospital_pk)
    with factory() as s:
        claim = try_claim_once(
            s,
            hospital_pk=hosp.hospital_pk,
            gateway_id="gw_test",
            lease_ttl_seconds=900,
        )
        s.commit()
    assert claim is not None
    assert claim.transfer_job.state == "claimed"
    assert claim.transfer_job.lease_owner == "gw_test"
    assert claim.transfer_job.attempt_count == 1


def test_empty_queue_returns_none(engine_and_factory, seeded_hospital) -> None:
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        claim = try_claim_once(
            s, hospital_pk=hosp.hospital_pk, gateway_id="gw_x", lease_ttl_seconds=60
        )
    assert claim is None


def test_sequential_claims_drain_queue(engine_and_factory, seeded_hospital) -> None:
    """Second caller gets nothing because the row is already claimed.

    This is the Python-side verification; true SKIP LOCKED concurrency
    requires Postgres and is covered by the integration fixture.
    """
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_job(s, hospital_pk=hosp.hospital_pk, tj_id="tj_once")
    with factory() as s:
        c1 = try_claim_once(
            s, hospital_pk=hosp.hospital_pk, gateway_id="gw_a", lease_ttl_seconds=900
        )
        s.commit()
        c2 = try_claim_once(
            s, hospital_pk=hosp.hospital_pk, gateway_id="gw_b", lease_ttl_seconds=900
        )
    assert c1 is not None
    assert c2 is None
