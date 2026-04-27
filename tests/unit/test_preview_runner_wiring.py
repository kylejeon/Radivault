"""Unit tests for ``radivault_gateway.transfer.runner.with_preview_pipeline``.

jpg-preview-defacing FR-PREVIEW-1 / B-1 (BLOCKER #1).

Coverage:

  * Flag off → preview wrapper is a no-op (upstream JobResult passthru,
    no audit / minio writes).
  * Flag on + mock_runner + empty SeriesInputsProvider → process_study
    is invoked once per study, manifest.preview is populated, and
    merge_preview_into_manifest produced the merged JobResult.
  * Flag on + provider error → study skipped, gateway pipeline doesn't
    crash (FR-DEFACE-8 invariant).
  * Flag on + ``ok=False`` upstream → preview is NOT run (don't run
    on failed jobs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from radivault_gateway.preview_pipeline import (
    FrameRecord,
    SeriesInput,
)
from radivault_gateway.transfer.claim import Claim
from radivault_gateway.transfer.consumer import JobResult
from radivault_gateway.transfer.progress import ProgressReporter
from radivault_gateway.transfer.runner import (
    mock_runner,
    with_preview_pipeline,
)


@dataclass
class _Minio:
    objects: dict[str, bytes] = field(default_factory=dict)
    buckets: set[str] = field(default_factory=set)

    def ensure_bucket(self, *, bucket: str) -> None:
        self.buckets.add(bucket)

    def put_jpeg(self, *, bucket: str, key: str, body: bytes) -> None:
        self.objects[key] = body


@dataclass
class _Audit:
    rows: list[dict] = field(default_factory=list)

    def write_audit(self, **kwargs) -> None:
        self.rows.append(kwargs)


@dataclass
class _Frames:
    rows: list[dict] = field(default_factory=list)

    def write_frame_rows(
        self, *, pseudo_study_uid, pseudo_series_uid, frames: list[FrameRecord]
    ) -> None:
        for f in frames:
            self.rows.append(
                {
                    "study": pseudo_study_uid,
                    "series": pseudo_series_uid,
                    "frame_idx": f.frame_idx,
                }
            )


def _claim(uids: list[str]) -> Claim:
    return Claim(
        transfer_job_id="tj_b1",
        order_id="ord_b1",
        hospital_id="hosp_b1",
        studies=[
            {"pseudo_study_uid": uid, "expected_instances": 1} for uid in uids
        ],
        lease_expires_at="2030-01-01T00:00:00Z",
        ruleset_version_required="v0.1.0",
        salt_version_required=1,
        cancel_requested=False,
    )


def _reporter() -> ProgressReporter:
    return ProgressReporter(interval_seconds=0)


def test_flag_off_passes_through_upstream(monkeypatch):
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "false")
    minio, audit, fw = _Minio(), _Audit(), _Frames()
    runner = with_preview_pipeline(
        mock_runner,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
    )
    out = runner(_claim(["RV-STD-A"]), _reporter())
    assert out.ok is True
    assert len(out.manifest) == 1
    # No preview block — upstream's manifest is unchanged.
    assert "preview" not in out.manifest[0]
    assert audit.rows == []
    assert minio.buckets == set()


def test_flag_on_empty_provider_attaches_preview_block(monkeypatch, tmp_path):
    """B-1 acceptance smoke — flag on + mock_runner exercises the
    new path, manifest.preview is populated, even with an empty
    series_inputs provider."""
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "true")
    minio, audit, fw = _Minio(), _Audit(), _Frames()
    runner = with_preview_pipeline(
        mock_runner,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
    )
    out = runner(_claim(["RV-STD-A"]), _reporter())
    assert out.ok is True
    assert len(out.manifest) == 1
    entry = out.manifest[0]
    assert "preview" in entry, "B-1: manifest entry must carry a preview block"
    preview = entry["preview"]
    assert preview["skipped"] is False
    assert preview["pipeline_version"] == "0.1.0"
    assert preview["series"] == []
    # process_study touched MinIO (ensure_bucket) even with no series
    # — that's the wire-up smoke we wanted.
    assert "radivault-previews" in minio.buckets


def test_flag_on_provider_returning_series_calls_process_study(monkeypatch, tmp_path):
    """Provider yields one US series → process_study returns 1 series
    in PreviewBatchResult → merged manifest carries it."""
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "true")
    minio, audit, fw = _Minio(), _Audit(), _Frames()

    series_dir = tmp_path / "ser-1"
    series_dir.mkdir()

    def provider(*, claim, manifest_entry):
        return [
            SeriesInput(
                pseudo_series_uid="RV-SER-1",
                series_num=1,
                series_dir=series_dir,
                modality="US",
                body_part="ABDOMEN",
            )
        ]

    runner = with_preview_pipeline(
        mock_runner,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        series_inputs_provider=provider,
    )
    out = runner(_claim(["RV-STD-A"]), _reporter())
    assert out.ok
    entry = out.manifest[0]
    preview = entry["preview"]
    assert len(preview["series"]) == 1
    s = preview["series"][0]
    assert s["pseudo_series_uid"] == "RV-SER-1"
    assert s["modality"] == "US"
    assert s["deface_decision"] == "not_required"
    # FR-DEFACE-4 — US is short-circuited, audit outcome=not_required
    assert audit.rows[0]["outcome"] == "not_required"


def test_flag_on_upstream_failure_skips_preview(monkeypatch):
    """Don't run preview on failed upstream jobs."""
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "true")
    minio, audit, fw = _Minio(), _Audit(), _Frames()

    def failing_upstream(claim, reporter):
        return JobResult(
            ok=False,
            manifest=[],
            reason_code="OTHER",
            reason_detail="upstream broke",
            retryable=True,
        )

    runner = with_preview_pipeline(
        failing_upstream,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
    )
    out = runner(_claim(["RV-STD-A"]), _reporter())
    assert out.ok is False
    assert audit.rows == []
    assert minio.buckets == set()


def test_flag_on_provider_crash_does_not_kill_runner(monkeypatch):
    """Provider exception → study is skipped, gateway pipeline still
    completes (FR-DEFACE-8 invariant: preview failures never propagate)."""
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "true")
    minio, audit, fw = _Minio(), _Audit(), _Frames()

    def bad_provider(*, claim, manifest_entry):
        raise RuntimeError("provider blew up")

    runner = with_preview_pipeline(
        mock_runner,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        series_inputs_provider=bad_provider,
    )
    out = runner(_claim(["RV-STD-A", "RV-STD-B"]), _reporter())
    assert out.ok is True
    # Both manifest entries survive; neither has a preview block.
    assert len(out.manifest) == 2
    for entry in out.manifest:
        assert "preview" not in entry


def test_flag_on_one_study_succeeds_one_fails_in_provider(monkeypatch, tmp_path):
    """Mixed: 2 studies, provider errors on study A, returns inputs for B.
    Result: B has a preview block, A does not, both ok=True."""
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "true")
    minio, audit, fw = _Minio(), _Audit(), _Frames()

    series_dir = tmp_path / "ser-b"
    series_dir.mkdir()

    def provider(*, claim, manifest_entry):
        if manifest_entry["pseudo_study_uid"] == "RV-STD-A":
            raise RuntimeError("A is bad")
        return [
            SeriesInput(
                pseudo_series_uid="RV-SER-B",
                series_num=1,
                series_dir=series_dir,
                modality="US",
                body_part="ABDOMEN",
            )
        ]

    runner = with_preview_pipeline(
        mock_runner,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        series_inputs_provider=provider,
    )
    out = runner(_claim(["RV-STD-A", "RV-STD-B"]), _reporter())
    assert out.ok is True
    by_uid = {e["pseudo_study_uid"]: e for e in out.manifest}
    assert "preview" not in by_uid["RV-STD-A"]
    assert "preview" in by_uid["RV-STD-B"]
    assert by_uid["RV-STD-B"]["preview"]["series"][0]["pseudo_series_uid"] == "RV-SER-B"
