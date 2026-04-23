"""Progress / complete / fail / reap lease logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from radivault_fulfillment.db.models import (
    Order,
    OrderItem,
    TransferJob,
    TransferJobDeadLetter,
)
from radivault_fulfillment.errors import (
    JobCounterRegress,
    JobLeaseExpired,
    JobLeaseOwnership,
    JobNotFound,
    JobStateConflict,
)
from radivault_fulfillment.jobs.lease import (
    complete_job,
    fail_job,
    reap_expired_leases,
    report_progress,
)


def _seed_order_and_claim(session, *, hospital_pk: int, tj_id: str, gateway_id: str):
    from radivault_search.db.models import Buyer

    buyer = Buyer(
        buyer_id=f"b_{tj_id}", name="b", contact_email="x@y", tier="preview", scope_json={}
    )
    session.add(buyer)
    session.flush()
    order = Order(
        order_id=f"ord_{tj_id}",
        buyer_pk=buyer.buyer_pk,
        kid="k" * 8,
        status="fetching",
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
        pseudo_study_uid="2.25.lease",
        hospital_pk=hospital_pk,
        source="on_demand",
        state="pending",
        n_instances=1,
        total_bytes=1024,
    )
    session.add(item)
    now = datetime.now(tz=UTC)
    job = TransferJob(
        transfer_job_id=tj_id,
        order_pk=order.order_pk,
        hospital_pk=hospital_pk,
        state="claimed",
        lease_owner=gateway_id,
        lease_expires_at=now + timedelta(minutes=15),
        claimed_at=now,
        attempt_count=1,
        studies=[{"pseudo_study_uid": "2.25.lease", "expected_instances": 1}],
        ruleset_version_required="v0.1.0",
        salt_version_required=1,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return order, job


def test_progress_extends_lease(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_p1", gateway_id="gw1")
    with factory() as s:
        new_lease, cancel_req = report_progress(
            s,
            transfer_job_id="tj_p1",
            gateway_id="gw1",
            n_fetched=5,
            n_deided=4,
            n_uploaded=3,
            lease_extend=True,
            lease_ttl_seconds=600,
        )
        s.commit()
        assert cancel_req is False
        job = s.query(TransferJob).filter_by(transfer_job_id="tj_p1").one()
        assert job.n_fetched == 5 and job.n_deided == 4 and job.n_uploaded == 3
        # Lease should be within ~10s of now+600s.
        delta = (new_lease - datetime.now(tz=UTC)).total_seconds()
        assert 500 < delta < 610


def test_progress_wrong_owner(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_p2", gateway_id="gw1")
    with factory() as s:
        with pytest.raises(JobLeaseOwnership):
            report_progress(
                s,
                transfer_job_id="tj_p2",
                gateway_id="someone_else",
                n_fetched=1,
                n_deided=0,
                n_uploaded=0,
                lease_extend=False,
                lease_ttl_seconds=60,
            )


def test_counter_regress(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_p3", gateway_id="gw1")
    with factory() as s:
        # first update to 5
        report_progress(
            s,
            transfer_job_id="tj_p3",
            gateway_id="gw1",
            n_fetched=5,
            n_deided=5,
            n_uploaded=5,
            lease_extend=True,
            lease_ttl_seconds=60,
        )
        s.commit()
    with factory() as s:
        with pytest.raises(JobCounterRegress):
            report_progress(
                s,
                transfer_job_id="tj_p3",
                gateway_id="gw1",
                n_fetched=3,
                n_deided=3,
                n_uploaded=3,
                lease_extend=False,
                lease_ttl_seconds=60,
            )


def test_complete_transitions_order(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_c1", gateway_id="gw1")
    with factory() as s:
        job, order_state = complete_job(
            s,
            transfer_job_id="tj_c1",
            gateway_id="gw1",
            manifest=[
                {
                    "pseudo_study_uid": "2.25.lease",
                    "n_instances": 1,
                    "total_bytes": 1024,
                    "status": "uploaded",
                    "central_job_ids": ["ingest_01"],
                }
            ],
        )
        s.commit()
        assert order_state == "staging_complete"
        assert job.state == "completed"
        order = s.query(Order).filter_by(order_id="ord_tj_c1").one()
        assert order.status == "staging_complete"


def test_fail_retryable_requeues(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_f1", gateway_id="gw1")
    with factory() as s:
        job, will_retry = fail_job(
            s,
            transfer_job_id="tj_f1",
            gateway_id="gw1",
            reason_code="PACS_UNAVAILABLE",
            details="connection timeout",
            retryable=True,
            max_retries=5,
        )
        s.commit()
    assert will_retry is True
    assert job.state == "queued"
    assert job.lease_owner is None


def test_fail_non_retryable_dlq(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_f2", gateway_id="gw1")
    with factory() as s:
        job, will_retry = fail_job(
            s,
            transfer_job_id="tj_f2",
            gateway_id="gw1",
            reason_code="BURNED_IN_BLOCKED",
            details="pixel stage blocked",
            retryable=False,
            max_retries=5,
        )
        s.commit()
        dlq = s.query(TransferJobDeadLetter).filter_by(transfer_job_pk=job.transfer_job_pk).first()
    assert will_retry is False
    assert job.state == "dead"
    assert dlq is not None
    assert dlq.reason_code == "BURNED_IN_BLOCKED"


def test_lease_reaper_requeues(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        order, job = _seed_order_and_claim(
            s, hospital_pk=hosp.hospital_pk, tj_id="tj_r1", gateway_id="gw1"
        )
        job.lease_expires_at = datetime.now(tz=UTC) - timedelta(minutes=30)
        s.commit()
    with factory() as s:
        requeued, dead = reap_expired_leases(s, max_retries=5)
        s.commit()
    assert (requeued, dead) == (1, 0)
    with factory() as s:
        job = s.query(TransferJob).filter_by(transfer_job_id="tj_r1").one()
    assert job.state == "queued"
    assert job.lease_owner is None


def test_lease_reaper_dlq_on_exhaustion(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        order, job = _seed_order_and_claim(
            s, hospital_pk=hosp.hospital_pk, tj_id="tj_r2", gateway_id="gw1"
        )
        job.lease_expires_at = datetime.now(tz=UTC) - timedelta(minutes=30)
        job.attempt_count = 5
        s.commit()
    with factory() as s:
        requeued, dead = reap_expired_leases(s, max_retries=5)
        s.commit()
    assert (requeued, dead) == (0, 1)


def test_progress_job_not_found(engine_and_factory):
    _, factory = engine_and_factory
    with factory() as s:
        with pytest.raises(JobNotFound):
            report_progress(
                s,
                transfer_job_id="tj_missing",
                gateway_id="gw1",
                n_fetched=0,
                n_deided=0,
                n_uploaded=0,
                lease_extend=False,
                lease_ttl_seconds=60,
            )


def test_progress_lease_expired(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_exp", gateway_id="gw1")
        j = s.query(TransferJob).filter_by(transfer_job_id="tj_exp").one()
        j.lease_expires_at = datetime.now(tz=UTC) - timedelta(minutes=1)
        s.commit()
    with factory() as s:
        with pytest.raises(JobLeaseExpired):
            report_progress(
                s,
                transfer_job_id="tj_exp",
                gateway_id="gw1",
                n_fetched=1,
                n_deided=0,
                n_uploaded=0,
                lease_extend=False,
                lease_ttl_seconds=60,
            )


def test_progress_state_conflict(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_order_and_claim(s, hospital_pk=hosp.hospital_pk, tj_id="tj_sc", gateway_id="gw1")
        j = s.query(TransferJob).filter_by(transfer_job_id="tj_sc").one()
        j.state = "completed"
        s.commit()
    with factory() as s:
        with pytest.raises(JobStateConflict):
            report_progress(
                s,
                transfer_job_id="tj_sc",
                gateway_id="gw1",
                n_fetched=1,
                n_deided=0,
                n_uploaded=0,
                lease_extend=False,
                lease_ttl_seconds=60,
            )
