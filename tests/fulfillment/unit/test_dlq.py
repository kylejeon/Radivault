"""DLQ helpers — resolve, requeue, count."""

from __future__ import annotations

from decimal import Decimal

import pytest

from radivault_fulfillment.db.models import (
    Order,
    TransferJob,
    TransferJobDeadLetter,
)
from radivault_fulfillment.jobs.dlq import (
    count_unresolved,
    requeue_from_dlq,
    resolve,
)


def _seed_dead_job(session, *, hospital_pk: int, tj_id: str) -> TransferJob:
    from radivault_search.db.models import Buyer

    buyer = Buyer(buyer_id=f"b_{tj_id}", name="b", contact_email="x", tier="preview", scope_json={})
    session.add(buyer)
    session.flush()
    order = Order(
        order_id=f"ord_{tj_id}",
        buyer_pk=buyer.buyer_pk,
        kid="k" * 8,
        status="failed",
        n_studies=1,
        total_bytes=1,
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
        state="dead",
        attempt_count=5,
        studies=[{"pseudo_study_uid": "2.25.x", "expected_instances": 1}],
        ruleset_version_required="v0.1.0",
        salt_version_required=1,
    )
    session.add(job)
    session.flush()
    dlq = TransferJobDeadLetter(
        transfer_job_pk=job.transfer_job_pk,
        reason_code="PACS_UNAVAILABLE",
        reason_detail="exhausted",
        attempts=5,
    )
    session.add(dlq)
    session.commit()
    session.refresh(job)
    return job


def test_count_unresolved(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_dead_job(s, hospital_pk=hosp.hospital_pk, tj_id="tj_dlq_a")
        _seed_dead_job(s, hospital_pk=hosp.hospital_pk, tj_id="tj_dlq_b")
    with factory() as s:
        assert count_unresolved(s) == 2


def test_requeue_from_dlq(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_dead_job(s, hospital_pk=hosp.hospital_pk, tj_id="tj_rq_1")
    with factory() as s:
        requeue_from_dlq(
            s, transfer_job_id="tj_rq_1", resolved_by="admin_kyle", reset_attempts=True
        )
        s.commit()
    with factory() as s:
        j = s.query(TransferJob).filter_by(transfer_job_id="tj_rq_1").one()
        dlq = s.query(TransferJobDeadLetter).filter_by(transfer_job_pk=j.transfer_job_pk).one()
    assert j.state == "queued"
    assert j.attempt_count == 0
    assert dlq.resolution == "requeued"
    assert dlq.resolved_at is not None


def test_requeue_rejects_live_job(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        job = _seed_dead_job(s, hospital_pk=hosp.hospital_pk, tj_id="tj_rq_2")
        job.state = "queued"
        s.commit()
    with factory() as s:
        with pytest.raises(ValueError):
            requeue_from_dlq(s, transfer_job_id="tj_rq_2", resolved_by="admin")


def test_resolve_closes_dlq(engine_and_factory, seeded_hospital):
    _, factory = engine_and_factory
    hosp, _ = seeded_hospital
    with factory() as s:
        _seed_dead_job(s, hospital_pk=hosp.hospital_pk, tj_id="tj_rq_3")
        dlq_pk = s.query(TransferJobDeadLetter).first().dlq_pk
    with factory() as s:
        resolved = resolve(s, dlq_pk=dlq_pk, resolved_by="admin", resolution="failed_final")
        s.commit()
    assert resolved.resolution == "failed_final"
