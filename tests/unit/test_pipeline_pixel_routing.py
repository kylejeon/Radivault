"""Pipeline-level integration tests for F-1 / C-1 (QA round 1 regression gap).

These tests wire a real ``Pipeline.run_once()`` against a stubbed PACS + upload
mock and assert that burn-in / face-risk studies flow through the pixel stage
(not the quarantine short-circuit) when ``cfg.deid.pixel.enabled=true``.

Previous unit tests exercised ``PixelDeidEngine.process_study`` directly; this
file closes the gap by covering ``Pipeline._process_study``'s routing logic.
"""

from __future__ import annotations

import importlib
import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from radivault_gateway.audit import AuditLogger
from radivault_gateway.config import GatewayConfig
from radivault_gateway.deid import DeidEngine
from radivault_gateway.deid.pixel import (
    OcrBox,
    PixelDeidConfig,
    PixelDeidEngine,
)
from radivault_gateway.deid.pixel.deface_engine import DefaceResult
from radivault_gateway.orchestrator import Pipeline
from radivault_gateway.pacs import FetchResult, StudySummary
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB, StudyState
from radivault_gateway.upload import UploadClient

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy not installed (pixel extras absent)",
)


@dataclass
class _FakePacs:
    studies: list[StudySummary]
    fetch_dir_src: Path

    def query_studies(self, *args, **kwargs):
        return self.studies

    def fetch_study(self, study_uid, out_dir):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for src in sorted(self.fetch_dir_src.glob("*.dcm")):
            shutil.copy(src, out / src.name)
        paths = sorted(out.glob("*.dcm"))
        return FetchResult(
            study_instance_uid=study_uid,
            instance_paths=paths,
            bytes_total=sum(p.stat().st_size for p in paths),
            duration_ms=5,
        )


class _FakeOcrEngine:
    engine_name = "fake_ocr"

    def __init__(self, boxes: list[OcrBox]):
        self._boxes = boxes
        self._call_count = 0

    def detect_text(self, image, *, languages):
        self._call_count += 1
        if self._call_count == 1:
            return list(self._boxes)
        return []  # residual recheck: clean

    def version(self) -> str:
        return "fake-1.0"


class _FakeLowConfOcrEngine:
    engine_name = "fake_ocr_lowconf"

    def detect_text(self, image, *, languages):
        return [OcrBox(x=0, y=0, w=4, h=4, text="x", confidence=0.1)]

    def version(self) -> str:
        return "fake-0.0"


class _FakeDefaceEngine:
    engine_name = "fake_deface"

    def __init__(self, ratio: float = 0.30):
        self._ratio = ratio

    def deface_volume(self, volume_path, out_path) -> DefaceResult:
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=self._ratio,
            duration_ms=100,
            library=self.engine_name,
        )

    def is_available(self) -> bool:
        return True

    def version(self) -> str:
        return "fake-2.0"


def _write_pixel_study(
    study_dir: Path, *, burned_in: str, modality: str, body_part: str = ""
) -> None:
    """Write a minimal multi-instance study with valid pixel data."""
    import numpy as np
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    study_dir.mkdir(parents=True, exist_ok=True)
    for i in range(2):
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
        file_meta.MediaStorageSOPInstanceUID = f"1.2.3.4.5.{i}"
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        path = study_dir / f"inst_{i}.dcm"
        ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.PatientName = "HONG^GIL"
        ds.PatientID = "P-PIXEL"
        ds.PatientBirthDate = "19800101"
        ds.PatientSex = "M"
        ds.StudyInstanceUID = f"1.2.840.studyrouting.{modality}"
        ds.SeriesInstanceUID = f"1.2.840.studyrouting.{modality}.1"
        ds.SOPInstanceUID = f"1.2.3.4.5.{i}"
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.Modality = modality
        ds.BurnedInAnnotation = burned_in
        ds.StudyDescription = "MR Brain Study"
        if body_part:
            ds.BodyPartExamined = body_part
        ds.StudyDate = "20260401"
        ds.SeriesDate = "20260401"
        arr = np.full((16, 16), 200, dtype="uint16")
        ds.Rows, ds.Columns = arr.shape
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.PixelData = arr.tobytes()
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.save_as(path, enforce_file_format=False)


def _build_config(tmp_path: Path) -> GatewayConfig:
    import yaml

    salt = tmp_path / "salt"
    salt.write_text("0123456789abcdef" * 2)
    data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
            "hospital_id": "hosp_test",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": {
            "base_url": "http://pacs.invalid",
            "auth": {"type": "bearer", "token": "tok"},
            "max_concurrency": 2,
            "poll_interval_seconds": 60,
            "query": {"modalities": ["US", "MR", "CT"], "lookback_days": 7},
        },
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt": f"${{file:{salt}}}",
            "salt_version": 1,
        },
        "staging": {
            "root": str(tmp_path / "stg"),
            "retention_hours": 72,
            "max_disk_pct": 99,
        },
        "state": {"db_path": str(tmp_path / "state.sqlite3")},
        "audit": {"path": str(tmp_path / "audit.log"), "anchor_interval_seconds": 3600},
        "central": {
            "base_url": "http://testserver",
            "upload_token": "tok-abc",
            "allow_insecure": True,
        },
        "logging": {"level": "INFO", "json": True},
    }
    cfg_path = tmp_path / "gateway.yml"
    cfg_path.write_text(yaml.safe_dump(data))
    from radivault_gateway.config import load_config

    return load_config(cfg_path)


def _build_pipeline_with_pixel(
    tmp_path: Path,
    monkeypatch,
    *,
    pixel_enabled: bool,
    pixel_engine: PixelDeidEngine | None,
    study_src: Path,
    modalities: list[str],
    study_uid: str,
) -> tuple[Pipeline, StateDB, GatewayConfig]:
    monkeypatch.setenv("MOCK_CENTRAL_DUMP", str(tmp_path / "dump"))
    monkeypatch.setenv("MOCK_CENTRAL_TOKEN", "tok-abc")
    import radivault_mock_central.main as mod

    importlib.reload(mod)
    test_client = TestClient(mod.app)

    cfg = _build_config(tmp_path)
    db = StateDB(cfg.state.db_path)
    db.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit = AuditLogger(cfg.audit.path, gateway_id=cfg.agent.gateway_id)
    staging = StagingManager(cfg.staging.root, max_disk_pct=cfg.staging.max_disk_pct)
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=db,
        retain=cfg.deid.retain_options,
        pixel_enabled=pixel_enabled,
        pixel_ocr_modalities=("SC", "OT", "US", "XA", "MG") if pixel_enabled else (),
    )
    pacs = _FakePacs(
        studies=[
            StudySummary(
                study_instance_uid=study_uid,
                patient_id="P-001",
                study_date="20260401",
                modalities_in_study=modalities,
                num_instances=2,
            )
        ],
        fetch_dir_src=study_src,
    )
    upload = UploadClient(
        "http://testserver", upload_token="tok-abc", max_retries=1, allow_insecure=True
    )

    def _bridge(request: httpx.Request) -> httpx.Response:
        resp = test_client.request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
            params=dict(request.url.params),
        )
        return httpx.Response(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
        )

    upload._client = httpx.Client(
        transport=httpx.MockTransport(_bridge),
        base_url="http://testserver",
        headers={"Authorization": "Bearer tok-abc"},
        timeout=30.0,
    )
    pipeline = Pipeline(
        cfg,
        state_db=db,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs=pacs,
        upload=upload,
        pixel=pixel_engine,
    )
    return pipeline, db, cfg


# ---- F-1 (C-1): burn-in routing when pixel enabled ----


def test_pipeline_routes_burn_in_to_pixel_when_enabled(tmp_path, monkeypatch):
    """Burn-in US study with pixel.enabled=true must proceed through pixel stage,
    NOT short-circuit to quarantine."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="YES", modality="US")

    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.residual_recheck = False
    cfg.defacing.enabled = False
    ocr = _FakeOcrEngine(boxes=[OcrBox(x=2, y=2, w=6, h=4, text="PATIENT", confidence=0.95)])
    pixel_engine = PixelDeidEngine(cfg, ocr_engine=ocr)

    pipeline, _, _ = _build_pipeline_with_pixel(
        tmp_path,
        monkeypatch,
        pixel_enabled=True,
        pixel_engine=pixel_engine,
        study_src=study_src,
        modalities=["US"],
        study_uid="1.2.3.US.BURN",
    )
    summary = pipeline.run_once()
    assert summary.quarantined == 0, "pixel.enabled=true must not quarantine burn-in"
    assert summary.uploaded == 1
    outcome = summary.outcomes[0]
    assert outcome.state == StudyState.UPLOADED


def test_pipeline_still_quarantines_burn_in_when_pixel_disabled(tmp_path, monkeypatch):
    """Bit-equivalence: pixel.enabled=false preserves v0.1 quarantine behaviour (AC-15)."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="YES", modality="US")

    pipeline, _, _ = _build_pipeline_with_pixel(
        tmp_path,
        monkeypatch,
        pixel_enabled=False,
        pixel_engine=None,
        study_src=study_src,
        modalities=["US"],
        study_uid="1.2.3.US.BURN.V1",
    )
    summary = pipeline.run_once()
    assert summary.quarantined == 1
    assert summary.uploaded == 0


def test_pipeline_quarantines_burn_in_on_low_confidence(tmp_path, monkeypatch):
    """OCR engine returns only low-confidence boxes → ERR_PIXEL_OCR_LOW_CONFIDENCE → quarantine."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="YES", modality="US")

    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.residual_recheck = False
    cfg.defacing.enabled = False
    cfg.ocr.confidence_threshold = 0.8
    pixel_engine = PixelDeidEngine(cfg, ocr_engine=_FakeLowConfOcrEngine())

    pipeline, _, _ = _build_pipeline_with_pixel(
        tmp_path,
        monkeypatch,
        pixel_enabled=True,
        pixel_engine=pixel_engine,
        study_src=study_src,
        modalities=["US"],
        study_uid="1.2.3.US.BURN.LOWCONF",
    )
    summary = pipeline.run_once()
    assert summary.uploaded == 0
    assert summary.quarantined == 1
    outcome = summary.outcomes[0]
    assert outcome.state == StudyState.PIXEL_FAILED
    assert outcome.reason == "ERR_PIXEL_OCR_LOW_CONFIDENCE"


# ---- F-1: defacing path routing ----


def test_pipeline_routes_head_ct_to_pixel_when_defacing_enabled(tmp_path, monkeypatch):
    """CT head study (no burn-in) with pixel.defacing.enabled=true → pixel stage runs."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="NO", modality="CT", body_part="HEAD")

    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.enabled = True
    cfg.defacing.min_removed_ratio = 0.10
    pixel_engine = PixelDeidEngine(cfg, deface_engine=_FakeDefaceEngine(ratio=0.30))

    pipeline, _, _ = _build_pipeline_with_pixel(
        tmp_path,
        monkeypatch,
        pixel_enabled=True,
        pixel_engine=pixel_engine,
        study_src=study_src,
        modalities=["CT"],
        study_uid="1.2.3.CT.HEAD",
    )
    summary = pipeline.run_once()
    assert summary.quarantined == 0
    assert summary.uploaded == 1


def test_pipeline_still_uploads_non_burn_study_when_pixel_disabled(tmp_path, monkeypatch):
    """Regression: pixel.enabled=false + no burn-in → v0.1 upload path unchanged."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="NO", modality="MR", body_part="BRAIN")

    pipeline, _, _ = _build_pipeline_with_pixel(
        tmp_path,
        monkeypatch,
        pixel_enabled=False,
        pixel_engine=None,
        study_src=study_src,
        modalities=["MR"],
        study_uid="1.2.3.MR.V1",
    )
    summary = pipeline.run_once()
    assert summary.uploaded == 1
    assert summary.quarantined == 0


def test_pipeline_quarantines_head_ct_on_low_removed_ratio(tmp_path, monkeypatch):
    """Defacing returns ratio below threshold → ERR_PIXEL_RESIDUAL_FACE_VOXELS → quarantine."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="NO", modality="CT", body_part="HEAD")

    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.enabled = True
    cfg.defacing.min_removed_ratio = 0.20
    pixel_engine = PixelDeidEngine(cfg, deface_engine=_FakeDefaceEngine(ratio=0.01))

    pipeline, _, _ = _build_pipeline_with_pixel(
        tmp_path,
        monkeypatch,
        pixel_enabled=True,
        pixel_engine=pixel_engine,
        study_src=study_src,
        modalities=["CT"],
        study_uid="1.2.3.CT.HEAD.LOW",
    )
    summary = pipeline.run_once()
    assert summary.quarantined == 1
    assert summary.outcomes[0].reason == "ERR_PIXEL_RESIDUAL_FACE_VOXELS"
