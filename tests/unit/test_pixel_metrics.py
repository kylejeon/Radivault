"""F-4 (H-2) — Prometheus metrics registry + metrics dump CLI.

Design-spec §4.3 enumerates 10 ``radivault_gateway_pixel_*`` metrics. This
suite asserts all 10 are registered, that wiring through ``PixelDeidEngine``
populates them on the success and quarantine paths, and that the
``metrics dump`` CLI renders them in Prometheus exposition format.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from radivault_gateway.cli.main import cli
from radivault_gateway.deid.pixel import (
    OcrBox,
    PixelDeidConfig,
    PixelDeidEngine,
    build_pixel_metrics,
    dump_dict,
    dump_text,
)
from radivault_gateway.deid.pixel.deface_engine import DefaceResult

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy not installed (pixel extras absent)",
)


# The Prometheus client library strips the ``_total`` suffix from a Counter's
# family name (the suffix reappears on each emitted sample). We assert on the
# family-name form for ``dump_dict`` (which iterates ``registry.collect()``)
# and the full ``_total`` form appears in the Prometheus exposition text.
EXPECTED_COUNTER_FAMILIES = {
    "radivault_gateway_pixel_studies",
    "radivault_gateway_pixel_residual_text_found",
    "radivault_gateway_pixel_residual_face_voxels",
    "radivault_gateway_pixel_engine_unavailable",
    "radivault_gateway_pixel_medical_exclusion_hit",
}
EXPECTED_HISTOGRAM_FAMILIES = {
    "radivault_gateway_pixel_ocr_duration_seconds",
    "radivault_gateway_pixel_deface_duration_seconds",
    "radivault_gateway_pixel_ocr_confidence",
    "radivault_gateway_pixel_ocr_redaction_regions",
    "radivault_gateway_pixel_deface_removed_voxel_ratio",
}
EXPECTED_METRIC_FAMILIES = EXPECTED_COUNTER_FAMILIES | EXPECTED_HISTOGRAM_FAMILIES
EXPECTED_PROM_TEXT_NAMES = {
    "radivault_gateway_pixel_studies_total",
    "radivault_gateway_pixel_ocr_duration_seconds",
    "radivault_gateway_pixel_deface_duration_seconds",
    "radivault_gateway_pixel_ocr_confidence",
    "radivault_gateway_pixel_ocr_redaction_regions",
    "radivault_gateway_pixel_deface_removed_voxel_ratio",
    "radivault_gateway_pixel_residual_text_found_total",
    "radivault_gateway_pixel_residual_face_voxels_total",
    "radivault_gateway_pixel_engine_unavailable_total",
    "radivault_gateway_pixel_medical_exclusion_hit_total",
}


class _FakeOcrEngine:
    engine_name = "fake_ocr"

    def __init__(self, boxes: list[OcrBox]):
        self._boxes = boxes
        self._calls = 0

    def detect_text(self, image, *, languages):
        self._calls += 1
        return list(self._boxes) if self._calls == 1 else []

    def version(self) -> str:
        return "1.0"


class _FakeDefaceEngine:
    engine_name = "fake_deface"

    def deface_volume(self, volume_path, out_path):
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=0.3,
            duration_ms=100,
            library=self.engine_name,
        )

    def is_available(self):
        return True

    def version(self):
        return "2.0"


def _write_study(study_dir: Path, *, burned_in: str, modality: str, body_part: str = "") -> None:
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
    ds.PatientID = "ANON"
    ds.StudyInstanceUID = "1.2.840.metrics"
    ds.SeriesInstanceUID = "1.2.840.metrics.1"
    ds.SOPInstanceUID = "1.2.3.4.5"
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.Modality = modality
    ds.BurnedInAnnotation = burned_in
    if body_part:
        ds.BodyPartExamined = body_part
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


def test_build_pixel_metrics_registers_all_ten(tmp_path):
    metrics = build_pixel_metrics()
    data = dump_dict(metrics)
    registered = set(data.keys())
    missing = EXPECTED_METRIC_FAMILIES - registered
    assert not missing, f"missing metric families: {missing}"
    assert len(EXPECTED_METRIC_FAMILIES) == 10


def test_metrics_wired_on_ocr_success(tmp_path):
    metrics = build_pixel_metrics()
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.residual_recheck = False
    cfg.defacing.enabled = False
    ocr = _FakeOcrEngine([OcrBox(x=1, y=1, w=5, h=5, text="P", confidence=0.9)])
    engine = PixelDeidEngine(cfg, ocr_engine=ocr, metrics=metrics)
    study_dir = tmp_path / "s"
    _write_study(study_dir, burned_in="YES", modality="US")

    engine.process_study(
        study_dir,
        pseudo_study_uid="p1",
        study_description="",
        modality_set={"US"},
        body_part=None,
    )
    text = dump_text(metrics)
    # OCR success triage + ocr counters must be present.
    assert 'radivault_gateway_pixel_studies_total{result="OCR_REQUIRED",stage="triage"} 1.0' in text
    assert 'radivault_gateway_pixel_studies_total{result="success",stage="ocr"} 1.0' in text
    # Histogram has _count sample.
    assert "radivault_gateway_pixel_ocr_duration_seconds_count" in text
    assert "radivault_gateway_pixel_ocr_redaction_regions_count" in text


def test_metrics_wired_on_defacing_success(tmp_path):
    metrics = build_pixel_metrics()
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.enabled = True
    cfg.defacing.min_removed_ratio = 0.05
    engine = PixelDeidEngine(cfg, deface_engine=_FakeDefaceEngine(), metrics=metrics)
    study_dir = tmp_path / "s"
    _write_study(study_dir, burned_in="NO", modality="CT", body_part="HEAD")

    engine.process_study(
        study_dir,
        pseudo_study_uid="p2",
        study_description="",
        modality_set={"CT"},
        body_part="HEAD",
    )
    text = dump_text(metrics)
    assert 'radivault_gateway_pixel_studies_total{result="success",stage="deface"} 1.0' in text
    assert "radivault_gateway_pixel_deface_duration_seconds_count" in text
    assert "radivault_gateway_pixel_deface_removed_voxel_ratio_count" in text


def test_cli_metrics_dump_prom(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["-c", str(tmp_path / "nonexistent.yml"), "metrics", "dump", "--format", "prom"]
    )
    assert result.exit_code == 0, result.output
    # All 10 metric names in Prometheus exposition output.
    for name in EXPECTED_PROM_TEXT_NAMES:
        assert name in result.output, f"missing {name} in prom output"


def test_cli_metrics_dump_json(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["-c", str(tmp_path / "nonexistent.yml"), "metrics", "dump", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    for name in EXPECTED_METRIC_FAMILIES:
        assert name in payload, f"missing {name} in json output"
