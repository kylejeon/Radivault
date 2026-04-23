"""F-5 (H-3, AC-14, AC-21) — audit sinks on quarantine fallback paths.

Previously ``pixel.deface.fallback_used`` only reached the WARN app log and
``audit_seq`` cross-reference was always NULL on pixel_audit_event rows. This
suite drives ``Pipeline._run_pixel_stage`` through low-confidence OCR,
residual-face-voxel quarantine, medical exclusion quarantine, and defacing
fallback-used paths and asserts:

1. ``AuditLogger.append`` was called with the expected event name.
2. ``pixel_audit_event`` row with the matching op exists and carries an
   ``audit_seq`` value that lines up with the audit.log entry.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
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
from radivault_gateway.deid.pixel.errors import PixelDeidEngineError
from radivault_gateway.orchestrator import Pipeline
from radivault_gateway.pacs import FetchResult, StudySummary
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB

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


def _write_pixel_study(
    study_dir: Path,
    *,
    burned_in: str,
    modality: str,
    body_part: str = "",
    study_description: str = "",
) -> None:
    import numpy as np
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    study_dir.mkdir(parents=True, exist_ok=True)
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    path = study_dir / "inst.dcm"
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "ANON"
    ds.PatientID = "P-AUDIT"
    ds.StudyInstanceUID = "1.2.840.audit"
    ds.SeriesInstanceUID = "1.2.840.audit.1"
    ds.SOPInstanceUID = "1.2.3.4.5"
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.Modality = modality
    ds.BurnedInAnnotation = burned_in
    if body_part:
        ds.BodyPartExamined = body_part
    if study_description:
        ds.StudyDescription = study_description
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
            "gateway_id": "gw_audit",
            "hospital_id": "hosp_audit",
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


def _build_pipeline(
    tmp_path: Path,
    monkeypatch,
    *,
    study_src: Path,
    modalities: list[str],
    pixel_engine: PixelDeidEngine,
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
        pixel_enabled=True,
        pixel_ocr_modalities=("SC", "OT", "US", "XA", "MG"),
    )
    pacs = _FakePacs(
        studies=[
            StudySummary(
                study_instance_uid=study_uid,
                patient_id="P-001",
                study_date="20260401",
                modalities_in_study=modalities,
                num_instances=1,
            )
        ],
        fetch_dir_src=study_src,
    )
    from radivault_gateway.upload import UploadClient

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


def _read_audit_events(audit_path: Path) -> list[dict]:
    events: list[dict] = []
    for line in audit_path.read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


class _FakeLowConfOcrEngine:
    engine_name = "fake_ocr_lowconf"

    def detect_text(self, image, *, languages):
        return [OcrBox(x=0, y=0, w=4, h=4, text="x", confidence=0.1)]

    def version(self) -> str:
        return "0"


class _LowRatioDefaceEngine:
    engine_name = "fake_deface"

    def deface_volume(self, volume_path, out_path):
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=0.01,
            duration_ms=10,
            library=self.engine_name,
        )

    def is_available(self):
        return True

    def version(self):
        return "0"


class _GoodDefaceEngine:
    engine_name = "fake_good"

    def deface_volume(self, volume_path, out_path):
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=0.30,
            duration_ms=100,
            library=self.engine_name,
        )

    def is_available(self):
        return True

    def version(self):
        return "2"


class _FailingPrimaryDefaceEngine:
    engine_name = "fake_primary_bad"

    def deface_volume(self, volume_path, out_path):
        raise PixelDeidEngineError("ERR_PIXEL_DEFACE_FAILURE", "primary broken")

    def is_available(self):
        return True

    def version(self):
        return "1"


def test_low_confidence_ocr_writes_audit_and_pixel_row(tmp_path, monkeypatch):
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="YES", modality="US")
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.residual_recheck = False
    cfg.defacing.enabled = False
    cfg.ocr.confidence_threshold = 0.8
    engine = PixelDeidEngine(cfg, ocr_engine=_FakeLowConfOcrEngine())

    pipeline, db, gwcfg = _build_pipeline(
        tmp_path,
        monkeypatch,
        study_src=study_src,
        modalities=["US"],
        pixel_engine=engine,
        study_uid="1.2.3.AUDIT.LOWCONF",
    )
    pipeline.run_once()

    # audit.log has pixel.quarantined with ERR_PIXEL_OCR_LOW_CONFIDENCE
    events = _read_audit_events(Path(gwcfg.audit.path))
    quarantined = [e for e in events if e["event"] == "pixel.quarantined"]
    assert quarantined, "expected pixel.quarantined event"
    assert quarantined[-1]["meta"]["code"] == "ERR_PIXEL_OCR_LOW_CONFIDENCE"
    expected_seq = quarantined[-1]["seq"]

    # pixel_audit_event row with op=quarantine + audit_seq cross-ref
    rows = db.list_pixel_audit_events(op="quarantine")
    assert rows
    assert any(r["reason"] == "ERR_PIXEL_OCR_LOW_CONFIDENCE" for r in rows)
    assert any(r["audit_seq"] == expected_seq for r in rows)


def test_residual_face_voxels_writes_audit_and_pixel_row(tmp_path, monkeypatch):
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="NO", modality="CT", body_part="HEAD")
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.enabled = True
    cfg.defacing.min_removed_ratio = 0.10
    engine = PixelDeidEngine(cfg, deface_engine=_LowRatioDefaceEngine())

    pipeline, db, gwcfg = _build_pipeline(
        tmp_path,
        monkeypatch,
        study_src=study_src,
        modalities=["CT"],
        pixel_engine=engine,
        study_uid="1.2.3.AUDIT.FACE",
    )
    pipeline.run_once()

    events = _read_audit_events(Path(gwcfg.audit.path))
    q = [e for e in events if e["event"] == "pixel.quarantined"]
    assert q
    assert q[-1]["meta"]["code"] == "ERR_PIXEL_RESIDUAL_FACE_VOXELS"
    rows = db.list_pixel_audit_events(op="quarantine")
    assert any(r["audit_seq"] == q[-1]["seq"] for r in rows)


def test_medical_exclusion_writes_audit_and_pixel_row(tmp_path, monkeypatch):
    """Medical exclusion fires as PixelQuarantineRequired and the pipeline writes
    a hash-chained audit event + pixel_audit_event row with matching audit_seq.

    The de-id metadata stage scrubs StudyDescription when it does not match the
    clean-descriptor whitelist — so a pipeline-level test has to feed the
    exclusion pattern through a ``monkeypatch`` of ``_sample_pixel_context`` so
    the pixel engine sees the original value rather than the scrubbed one.
    """
    import radivault_gateway.orchestrator.pipeline as pipeline_mod

    study_src = tmp_path / "src"
    _write_pixel_study(
        study_src,
        burned_in="NO",
        modality="CT",
        body_part="HEAD",
    )
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.enabled = True
    engine = PixelDeidEngine(cfg, deface_engine=_GoodDefaceEngine())

    monkeypatch.setattr(
        pipeline_mod,
        "_sample_pixel_context",
        lambda staging_dir: ("Dental CBCT maxilla", "HEAD"),
    )

    pipeline, db, gwcfg = _build_pipeline(
        tmp_path,
        monkeypatch,
        study_src=study_src,
        modalities=["CT"],
        pixel_engine=engine,
        study_uid="1.2.3.AUDIT.EXCL",
    )
    pipeline.run_once()

    events = _read_audit_events(Path(gwcfg.audit.path))
    q = [e for e in events if e["event"] == "pixel.quarantined"]
    assert q
    assert q[-1]["meta"]["code"] == "ERR_PIXEL_MEDICAL_EXCLUSION"
    rows = db.list_pixel_audit_events(op="quarantine")
    assert any(r["audit_seq"] == q[-1]["seq"] for r in rows)


def test_defacing_fallback_used_writes_hash_chained_audit_event(tmp_path, monkeypatch):
    """AC-14: successful fallback emits pixel.deface.fallback_used to audit.log."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="NO", modality="MR", body_part="HEAD")
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.fallback = True
    engine = PixelDeidEngine(
        cfg,
        deface_engine=_FailingPrimaryDefaceEngine(),
        fallback_deface_engine=_GoodDefaceEngine(),
    )

    pipeline, db, gwcfg = _build_pipeline(
        tmp_path,
        monkeypatch,
        study_src=study_src,
        modalities=["MR"],
        pixel_engine=engine,
        study_uid="1.2.3.AUDIT.FALLBACK",
    )
    pipeline.run_once()

    events = _read_audit_events(Path(gwcfg.audit.path))
    fb = [e for e in events if e["event"] == "pixel.deface.fallback_used"]
    assert fb, "expected pixel.deface.fallback_used audit event"
    assert fb[-1]["meta"]["fallback_library"] == "fake_good"
    assert fb[-1]["meta"]["primary_error_code"] == "ERR_PIXEL_DEFACE_FAILURE"

    # pixel_audit_event row with op=deface, outcome=fallback, audit_seq set
    rows = db.list_pixel_audit_events(op="deface")
    assert any(r["outcome"] == "fallback" and r["audit_seq"] == fb[-1]["seq"] for r in rows)


def test_success_path_writes_audit_seq_on_pixel_rows(tmp_path, monkeypatch):
    """AC-21: successful pixel completion pixel_audit_event rows carry audit_seq."""
    study_src = tmp_path / "src"
    _write_pixel_study(study_src, burned_in="NO", modality="CT", body_part="HEAD")
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.enabled = True
    engine = PixelDeidEngine(cfg, deface_engine=_GoodDefaceEngine())

    pipeline, db, gwcfg = _build_pipeline(
        tmp_path,
        monkeypatch,
        study_src=study_src,
        modalities=["CT"],
        pixel_engine=engine,
        study_uid="1.2.3.AUDIT.OK",
    )
    pipeline.run_once()

    events = _read_audit_events(Path(gwcfg.audit.path))
    completed = [e for e in events if e["event"] == "pixel.completed"]
    assert completed
    completed_seq = completed[-1]["seq"]
    rows = db.list_pixel_audit_events()
    # All non-recovery rows for this study should reference the completed seq.
    assert any(r["audit_seq"] == completed_seq for r in rows)
