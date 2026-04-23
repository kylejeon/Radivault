"""Gateway transfer subsystem — unit tests with a mock ClaimClient.

Tests assert that (a) the consumer exits early when ``enabled=false``,
(b) empty-queue response returns action=empty_queue, (c) a successful
job end-to-end calls complete, (d) a runner-raised exception triggers
the fail endpoint, (e) progress reporter schedules lease renewal.
"""

from __future__ import annotations

from radivault_gateway.transfer.claim import Claim
from radivault_gateway.transfer.config import TransferConfig
from radivault_gateway.transfer.consumer import JobResult, TransferConsumer
from radivault_gateway.transfer.progress import ProgressReporter


class FakeClaimClient:
    def __init__(self, claim: Claim | None = None):
        self._claim = claim
        self.fail_calls: list[dict] = []
        self.complete_calls: list[dict] = []

    def claim(self, *, wait_seconds: int = 30) -> Claim | None:
        return self._claim

    def complete(self, **kwargs) -> dict:
        self.complete_calls.append(kwargs)
        return {"state": "completed"}

    def fail(self, **kwargs) -> dict:
        self.fail_calls.append(kwargs)
        return {"state": "queued"}

    def progress(self, **kwargs) -> dict:
        return {"lease_expires_at": "2030-01-01T00:00:00Z", "cancel_requested": False}

    def close(self) -> None:
        pass


def _claim() -> Claim:
    return Claim(
        transfer_job_id="tj_gw_01",
        order_id="ord_gw_01",
        hospital_id="hosp_abc",
        studies=[{"pseudo_study_uid": "2.25.g.1", "expected_instances": 2}],
        lease_expires_at="2030-01-01T00:00:00Z",
        ruleset_version_required="v0.1.0",
        salt_version_required=1,
        cancel_requested=False,
    )


def test_consumer_disabled_by_default():
    cfg = TransferConfig()  # enabled=False
    assert cfg.enabled is False
    consumer = TransferConsumer(
        config=cfg,
        client=FakeClaimClient(),
        runner=lambda c, r: JobResult(ok=True, manifest=[]),
    )
    assert consumer.run_once() == {"action": "disabled"}


def test_consumer_empty_queue():
    cfg = TransferConfig(enabled=True, auth_token="tok")
    consumer = TransferConsumer(
        config=cfg,
        client=FakeClaimClient(claim=None),
        runner=lambda c, r: JobResult(ok=True, manifest=[]),
    )
    assert consumer.run_once() == {"action": "empty_queue"}


def test_consumer_happy_path_calls_complete():
    cfg = TransferConfig(enabled=True, auth_token="tok")
    client = FakeClaimClient(claim=_claim())

    def runner(c: Claim, r: ProgressReporter) -> JobResult:
        return JobResult(
            ok=True,
            manifest=[
                {
                    "pseudo_study_uid": "2.25.g.1",
                    "n_instances": 2,
                    "total_bytes": 1024,
                    "status": "uploaded",
                    "central_job_ids": ["ingest_1"],
                }
            ],
        )

    consumer = TransferConsumer(config=cfg, client=client, runner=runner)
    outcome = consumer.run_once()
    assert outcome["action"] == "complete"
    assert client.complete_calls
    assert client.complete_calls[0]["transfer_job_id"] == "tj_gw_01"


def test_consumer_runner_exception_calls_fail():
    cfg = TransferConfig(enabled=True, auth_token="tok")
    client = FakeClaimClient(claim=_claim())

    def runner(c: Claim, r: ProgressReporter) -> JobResult:
        raise RuntimeError("PACS down")

    consumer = TransferConsumer(config=cfg, client=client, runner=runner)
    outcome = consumer.run_once()
    assert outcome["action"] == "fail"
    assert client.fail_calls
    assert client.fail_calls[0]["reason_code"] == "OTHER"
    assert client.fail_calls[0]["retryable"] is True


def test_consumer_runner_explicit_failure_report():
    cfg = TransferConfig(enabled=True, auth_token="tok")
    client = FakeClaimClient(claim=_claim())

    def runner(c: Claim, r: ProgressReporter) -> JobResult:
        return JobResult(
            ok=False,
            manifest=[],
            reason_code="BURNED_IN_BLOCKED",
            reason_detail="pixel abort",
            retryable=False,
        )

    consumer = TransferConsumer(config=cfg, client=client, runner=runner)
    outcome = consumer.run_once()
    assert outcome["action"] == "fail"
    assert client.fail_calls[0]["reason_code"] == "BURNED_IN_BLOCKED"
    assert client.fail_calls[0]["retryable"] is False


def test_progress_reporter_due_and_payload():
    rep = ProgressReporter(interval_seconds=0, lease_extend_every=2)
    rep.record(fetched=2, deided=1)
    assert rep.due(now_fn=lambda: 10.0) is True
    p1 = rep.next_payload(now_fn=lambda: 10.0)
    assert p1["n_fetched"] == 2 and p1["n_deided"] == 1
    assert p1["lease_extend"] is False  # first call
    rep.record(uploaded=1)
    p2 = rep.next_payload(now_fn=lambda: 20.0)
    assert p2["lease_extend"] is True  # every 2nd call


def test_transfer_config_defaults_are_disabled():
    cfg = TransferConfig()
    # Top-of-spec invariant — Flow A regression guard.
    assert cfg.enabled is False
    assert cfg.max_concurrent_jobs == 2
