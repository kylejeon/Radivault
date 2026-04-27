"""Unit tests for radivault_gateway.preview_pipeline.

Coverage targets (jpg-preview-defacing dev-spec §10):

- FR-DEFACE-1 / AC-4 / AC-5 / AC-6 / AC-7 truth table for ``decide_deface``.
- FR-PREVIEW-3 feature-flag gate.
- FR-DEFACE-8 sidecar-failure quarantine path (4xx vs 5xx).
- FR-DEFACE-8 sidecar-unhealthy short-circuit.
- FR-PREVIEW-7 burned-in series-level skip.
- Manifest shape — series + frames count match.

The sidecar is faked via a ``DefaceClient`` shim so the suite never
needs a live AFNI container.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from radivault_gateway.deface_client import (
    QUARANTINE_INPUT,
    QUARANTINE_RUNTIME,
    DefaceFailure,
    DefaceFrame,
    DefaceSuccess,
)
from radivault_gateway.preview_pipeline import (
    FrameRecord,
    PIPELINE_VERSION,
    PreviewBatchResult,
    SeriesInput,
    decide_deface,
    is_pipeline_enabled,
    preview_key,
    process_study,
)


# ---------------------------------------------------------------------------
# decide_deface truth table (FR-DEFACE-1, AC-4..AC-7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "modality,body_part,study_description,protocol_name,expected_decision,reason_starts",
    [
        # AC-4
        ("MR", "BRAIN", None, None, "required", "BodyPartExamined=BRAIN"),
        # AC-5
        (
            "MR",
            None,
            "Brain MRI w/ contrast",
            None,
            "required",
            "regex:StudyDescription=Brain MRI",
        ),
        # ProtocolName regex fallback
        (
            "CT",
            None,
            None,
            "Cervical spine helical",
            "required",
            "regex:ProtocolName=Cervical",
        ),
        # AC-6
        ("US", "ABDOMEN", None, None, "not_required", "modality=US"),
        # AC-7
        ("CT", "CHEST", None, None, "not_required", "BodyPartExamined=CHEST"),
        # CT NECK -> required
        ("CT", "NECK", None, None, "required", "BodyPartExamined=NECK"),
        # FR-DEFACE-4 — PT, NM, MG, CR, DR, DX
        ("PT", None, None, None, "not_required", "modality=PT"),
        ("MG", None, None, None, "not_required", "modality=MG"),
        # Modality outside CT/MR/US/MG/CR/DR/DX/NM/PT -> skipped
        ("SR", None, None, None, "skipped_unsupported_modality", "modality=SR"),
        # No modality at all
        (
            "",
            None,
            None,
            None,
            "skipped_unsupported_modality",
            "modality=unknown",
        ),
        # No body part, no description / protocol -> not_required
        (
            "CT",
            None,
            None,
            None,
            "not_required",
            "no_body_part_no_regex_match",
        ),
        # Body part absent but description matches multiple tokens
        (
            "CT",
            None,
            "head/neck angio",
            None,
            "required",
            "regex:StudyDescription=",
        ),
    ],
)
def test_decide_deface_truth_table(
    modality, body_part, study_description, protocol_name,
    expected_decision, reason_starts,
):
    decision, reason = decide_deface(
        modality=modality,
        body_part=body_part,
        study_description=study_description,
        protocol_name=protocol_name,
    )
    assert decision == expected_decision
    assert reason.startswith(reason_starts), (
        f"reason={reason!r} did not start with {reason_starts!r}"
    )


# ---------------------------------------------------------------------------
# Feature flag (FR-PREVIEW-3)
# ---------------------------------------------------------------------------


def test_is_pipeline_enabled_default_off(monkeypatch):
    monkeypatch.delenv("PREVIEW_PIPELINE_ENABLED", raising=False)
    assert is_pipeline_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "ON"])
def test_is_pipeline_enabled_truthy(monkeypatch, val):
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", val)
    assert is_pipeline_enabled() is True


@pytest.mark.parametrize("val", ["0", "false", "no", "off", ""])
def test_is_pipeline_enabled_falsy(monkeypatch, val):
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", val)
    assert is_pipeline_enabled() is False


# ---------------------------------------------------------------------------
# Key layout (FR-PREVIEW-10)
# ---------------------------------------------------------------------------


def test_preview_key_format():
    assert (
        preview_key("RV-STD-abc", "RV-SER-def", 0)
        == "previews/RV-STD-abc/RV-SER-def/0000.jpg"
    )
    assert (
        preview_key("RV-STD-abc", "RV-SER-def", 9999)
        == "previews/RV-STD-abc/RV-SER-def/9999.jpg"
    )


# ---------------------------------------------------------------------------
# Fakes for end-to-end pipeline tests
# ---------------------------------------------------------------------------


@dataclass
class _FakeMinio:
    objects: dict[str, bytes] = field(default_factory=dict)
    buckets: set[str] = field(default_factory=set)

    def ensure_bucket(self, *, bucket: str) -> None:
        self.buckets.add(bucket)

    def put_jpeg(self, *, bucket: str, key: str, body: bytes) -> None:
        assert bucket == "radivault-previews", bucket
        self.objects[key] = body


@dataclass
class _FakeAuditWriter:
    rows: list[dict] = field(default_factory=list)

    def write_audit(self, **kwargs) -> None:
        self.rows.append(kwargs)


@dataclass
class _FakeFrameWriter:
    rows: list[dict] = field(default_factory=list)

    def write_frame_rows(
        self,
        *,
        pseudo_study_uid: str,
        pseudo_series_uid: str,
        frames: list[FrameRecord],
    ) -> None:
        for f in frames:
            self.rows.append(
                {
                    "study": pseudo_study_uid,
                    "series": pseudo_series_uid,
                    "frame_idx": f.frame_idx,
                    "key": f.minio_key,
                    "phi_scrub_method": f.phi_scrub_method,
                }
            )


@dataclass
class _FakeDefaceClient:
    healthy: bool = True
    response: object = None  # DefaceSuccess | DefaceFailure | None

    def healthz(self) -> bool:
        return self.healthy

    def deface_series(self, *, dicom_dir: Path, timeout_s: int | None = None):
        if self.response is None:
            return DefaceFailure(
                quarantine_reason=QUARANTINE_RUNTIME,
                error_code="NO_FAKE_RESPONSE",
                detail="test forgot to set _FakeDefaceClient.response",
                http_status=500,
            )
        return self.response


# ---------------------------------------------------------------------------
# Pipeline-level paths
# ---------------------------------------------------------------------------


def _enable(monkeypatch):
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "true")


def test_flag_off_returns_skipped(monkeypatch):
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "false")
    minio = _FakeMinio()
    audit = _FakeAuditWriter()
    fw = _FakeFrameWriter()
    out = process_study(
        pseudo_study_uid="RV-STD-x",
        series_inputs=[],
        study_description=None,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
    )
    assert out.skipped is True
    assert out.reason == "flag_off"
    assert out.series == []
    # No bucket touched, no audit row written.
    assert not minio.buckets
    assert audit.rows == []


def test_us_modality_short_circuits_to_not_required(monkeypatch, tmp_path):
    """AC-6 — Modality=US: not_required, no sidecar call, audit
    outcome=not_required, no frames."""
    _enable(monkeypatch)
    series_dir = tmp_path / "ser-us"
    series_dir.mkdir()
    minio = _FakeMinio()
    audit = _FakeAuditWriter()
    fw = _FakeFrameWriter()
    deface = _FakeDefaceClient(
        healthy=True,
        response=DefaceFailure(
            quarantine_reason=QUARANTINE_RUNTIME,
            error_code="should_not_be_called",
            detail="x",
            http_status=500,
        ),
    )
    out = process_study(
        pseudo_study_uid="RV-STD-us",
        series_inputs=[
            SeriesInput(
                pseudo_series_uid="RV-SER-us-1",
                series_num=1,
                series_dir=series_dir,
                modality="US",
                body_part="ABDOMEN",
            ),
        ],
        study_description=None,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        deface_client=deface,
    )
    assert len(out.series) == 1
    s = out.series[0]
    assert s.deface_decision == "not_required"
    assert s.preview_status in {"generated", "skipped"}
    # Sidecar response was never consumed (only ever returned a fake
    # error). The pipeline did not call deface_series — we infer this
    # from audit.outcome.
    assert audit.rows[0]["outcome"] == "not_required"
    assert audit.rows[0]["phi_scrub_method"] == "none_required" or (
        audit.rows[0]["phi_scrub_method"] == "none_required"
        and audit.rows[0]["error_code"] is None
    )


def test_required_series_4xx_quarantines_input(monkeypatch, tmp_path):
    """FR-DEFACE-8 — sidecar 4xx = quarantine_input, no retry, no frames."""
    _enable(monkeypatch)
    series_dir = tmp_path / "ser-head"
    series_dir.mkdir()
    minio = _FakeMinio()
    audit = _FakeAuditWriter()
    fw = _FakeFrameWriter()

    fail = DefaceFailure(
        quarantine_reason=QUARANTINE_INPUT,
        error_code="invalid_input",
        detail="dicom corrupt",
        http_status=400,
    )

    class OneShotClient:
        healthy = True
        call_count = 0

        def healthz(self):
            return True

        def deface_series(self, *, dicom_dir, timeout_s=None):
            OneShotClient.call_count += 1
            return fail

    out = process_study(
        pseudo_study_uid="RV-STD-h",
        series_inputs=[
            SeriesInput(
                pseudo_series_uid="RV-SER-h-1",
                series_num=1,
                series_dir=series_dir,
                modality="CT",
                body_part="HEAD",
            ),
        ],
        study_description=None,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        deface_client=OneShotClient(),
    )
    assert OneShotClient.call_count == 1, "4xx must NOT retry"
    s = out.series[0]
    assert s.preview_status == "quarantined"
    assert s.frame_count == 0
    assert audit.rows[0]["outcome"] == "quarantine_input"
    assert audit.rows[0]["phi_scrub_method"] == "deface_failed_input"
    assert audit.rows[0]["error_detail"] == "dicom corrupt"


def test_required_series_5xx_retries_once_then_quarantines(monkeypatch, tmp_path):
    """FR-DEFACE-8 — sidecar 5xx = quarantine_runtime + 1 retry, then
    quarantine. Audit row error_code=AFNI_CRASH.
    """
    _enable(monkeypatch)
    series_dir = tmp_path / "ser-h2"
    series_dir.mkdir()
    minio = _FakeMinio()
    audit = _FakeAuditWriter()
    fw = _FakeFrameWriter()

    fail = DefaceFailure(
        quarantine_reason=QUARANTINE_RUNTIME,
        error_code="afni_crashed",
        detail="afni dumped core",
        http_status=500,
    )

    class TwoShotClient:
        healthy = True
        call_count = 0

        def healthz(self):
            return True

        def deface_series(self, *, dicom_dir, timeout_s=None):
            TwoShotClient.call_count += 1
            return fail

    out = process_study(
        pseudo_study_uid="RV-STD-h2",
        series_inputs=[
            SeriesInput(
                pseudo_series_uid="RV-SER-h2-1",
                series_num=1,
                series_dir=series_dir,
                modality="MR",
                body_part="BRAIN",
            ),
        ],
        study_description=None,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        deface_client=TwoShotClient(),
    )
    assert TwoShotClient.call_count == 2, "5xx must retry exactly once"
    s = out.series[0]
    assert s.preview_status == "quarantined"
    assert audit.rows[0]["outcome"] == "quarantine_runtime"
    assert audit.rows[0]["error_code"] == "AFNI_CRASH"


def test_sidecar_unhealthy_quarantines_required_only(monkeypatch, tmp_path):
    """FR-DEFACE-8 — when sidecar healthz=False the pipeline marks
    deface-required series as quarantined immediately AND keeps
    processing not_required series.
    """
    _enable(monkeypatch)
    head_dir = tmp_path / "head"
    head_dir.mkdir()
    chest_dir = tmp_path / "chest"
    chest_dir.mkdir()
    minio = _FakeMinio()
    audit = _FakeAuditWriter()
    fw = _FakeFrameWriter()

    out = process_study(
        pseudo_study_uid="RV-STD-mix",
        series_inputs=[
            SeriesInput(
                pseudo_series_uid="RV-SER-h",
                series_num=1,
                series_dir=head_dir,
                modality="CT",
                body_part="HEAD",
            ),
            SeriesInput(
                pseudo_series_uid="RV-SER-c",
                series_num=2,
                series_dir=chest_dir,
                modality="CT",
                body_part="CHEST",
            ),
        ],
        study_description=None,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        deface_client=_FakeDefaceClient(healthy=False),
    )
    head, chest = out.series
    assert head.preview_status == "quarantined"
    assert audit.rows[0]["outcome"] == "quarantine_runtime"
    assert audit.rows[0]["error_code"] == "SIDECAR_UNHEALTHY"
    # Chest CT proceeds via local render — but no DICOM was actually
    # placed in chest_dir, so local render emits 0 frames -> skipped.
    # The point is that the pipeline DID NOT short-circuit on chest.
    assert chest.deface_decision == "not_required"


def test_required_series_success_emits_frames_and_uploads(monkeypatch, tmp_path):
    """Happy path — sidecar 200 -> per-frame upload + DB rows. AC-2/AC-3."""
    _enable(monkeypatch)
    series_dir = tmp_path / "ser-h3"
    series_dir.mkdir()
    minio = _FakeMinio()
    audit = _FakeAuditWriter()
    fw = _FakeFrameWriter()

    success = DefaceSuccess(
        frames=[
            DefaceFrame(frame_idx=0, jpeg_bytes=b"\xff\xd8\xff fake0"),
            DefaceFrame(frame_idx=1, jpeg_bytes=b"\xff\xd8\xff fake1"),
            DefaceFrame(frame_idx=2, jpeg_bytes=b"\xff\xd8\xff fake2"),
        ],
        afni_version="AFNI_24.0.00",
        sidecar_image_tag="radivault/deface-sidecar:0.1.0",
        duration_ms=30_000,
        warning=None,
    )
    out = process_study(
        pseudo_study_uid="RV-STD-h3",
        series_inputs=[
            SeriesInput(
                pseudo_series_uid="RV-SER-h3",
                series_num=1,
                series_dir=series_dir,
                modality="CT",
                body_part="HEAD",
            ),
        ],
        study_description=None,
        minio_client=minio,
        audit_writer=audit,
        frame_writer=fw,
        deface_client=_FakeDefaceClient(healthy=True, response=success),
    )
    s = out.series[0]
    assert s.preview_status == "generated"
    assert s.frame_count == 3
    assert s.phi_scrub_method == "afni_refacer_v0_7"

    # MinIO got 3 keys with the canonical layout.
    assert sorted(minio.objects.keys()) == [
        "previews/RV-STD-h3/RV-SER-h3/0000.jpg",
        "previews/RV-STD-h3/RV-SER-h3/0001.jpg",
        "previews/RV-STD-h3/RV-SER-h3/0002.jpg",
    ]
    # Frame writer got 3 rows.
    assert len(fw.rows) == 3
    # Audit row outcome=success and pipeline_version=0.1.0.
    assert audit.rows[0]["outcome"] == "success"
    assert audit.rows[0]["pipeline_version"] == PIPELINE_VERSION
    assert audit.rows[0]["sidecar_image_tag"] == "radivault/deface-sidecar:0.1.0"
    assert audit.rows[0]["afni_version"] == "AFNI_24.0.00"


def test_pipeline_returns_dataclass_not_dict(monkeypatch):
    """``PreviewBatchResult`` is the explicit return type — make sure
    callers can rely on it being a dataclass instance."""
    monkeypatch.setenv("PREVIEW_PIPELINE_ENABLED", "false")
    out = process_study(
        pseudo_study_uid="X",
        series_inputs=[],
        study_description=None,
        minio_client=_FakeMinio(),
        audit_writer=_FakeAuditWriter(),
        frame_writer=_FakeFrameWriter(),
    )
    assert isinstance(out, PreviewBatchResult)
