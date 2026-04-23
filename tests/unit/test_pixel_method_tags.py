"""F-2 (C-2, AC-27 + AC-28) DICOM de-id method tag stamping tests.

After pixel OCR redaction, each mutated DICOM must carry ``PixelRedacted`` in
``(0012,0063) DeidentificationMethod`` and code ``113101`` in the
``(0012,0064) DeidentificationMethodCodeSequence``. After defacing, the same
tags must carry ``Defaced`` and the private code ``RV_DEFACE_01``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from radivault_gateway.deid.pixel import (
    OcrBox,
    PixelDeidConfig,
    PixelDeidEngine,
)
from radivault_gateway.deid.pixel.deface_engine import DefaceResult

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy not installed (pixel extras absent)",
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
        return []

    def version(self) -> str:
        return "fake-1.0"


class _FakeDefaceEngine:
    engine_name = "fake_deface"

    def deface_volume(self, volume_path, out_path) -> DefaceResult:
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=0.30,
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
        ds.StudyInstanceUID = f"1.2.840.tagstamp.{modality}"
        ds.SeriesInstanceUID = f"1.2.840.tagstamp.{modality}.1"
        ds.SOPInstanceUID = f"1.2.3.4.5.{i}"
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.Modality = modality
        ds.BurnedInAnnotation = burned_in
        ds.StudyDescription = "MR Brain Study"
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


def test_ocr_success_stamps_pixel_redacted_tag(tmp_path):
    """AC-27 / FR-18: post-OCR DICOM has (0012,0063) PixelRedacted + (0012,0064) 113101."""
    import pydicom

    study_dir = tmp_path / "study"
    _write_pixel_study(study_dir, burned_in="YES", modality="US")

    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.residual_recheck = False
    cfg.defacing.enabled = False
    ocr = _FakeOcrEngine(boxes=[OcrBox(x=2, y=2, w=6, h=4, text="PATIENT", confidence=0.95)])
    engine = PixelDeidEngine(cfg, ocr_engine=ocr)

    engine.process_study(
        study_dir,
        pseudo_study_uid="pseudo-tag-1",
        study_description="US pelvic",
        modality_set={"US"},
        body_part=None,
    )

    # Re-read each DICOM; at least the mutated file should carry the tags.
    stamped_any = False
    for path in sorted(study_dir.rglob("*.dcm")):
        ds = pydicom.dcmread(path, force=False)
        method = str(getattr(ds, "DeidentificationMethod", "") or "")
        if "PixelRedacted" in method:
            stamped_any = True
            seq = list(getattr(ds, "DeidentificationMethodCodeSequence", []) or [])
            codes = {getattr(item, "CodeValue", None) for item in seq}
            assert "113101" in codes, f"expected 113101, got {codes}"
    assert stamped_any, "at least one DICOM must carry PixelRedacted after OCR"


def test_defacing_success_stamps_defaced_tag(tmp_path):
    """AC-28 / FR-18: post-deface DICOMs carry (0012,0063) Defaced + (0012,0064) RV_DEFACE_01."""
    import pydicom

    study_dir = tmp_path / "study"
    _write_pixel_study(study_dir, burned_in="NO", modality="CT", body_part="HEAD")

    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.enabled = True
    cfg.defacing.min_removed_ratio = 0.10
    engine = PixelDeidEngine(cfg, deface_engine=_FakeDefaceEngine())

    engine.process_study(
        study_dir,
        pseudo_study_uid="pseudo-tag-2",
        study_description="CT Head",
        modality_set={"CT"},
        body_part="HEAD",
    )

    for path in sorted(study_dir.rglob("*.dcm")):
        ds = pydicom.dcmread(path, force=False)
        method = str(getattr(ds, "DeidentificationMethod", "") or "")
        assert "Defaced" in method, f"missing Defaced substring in {path.name}: {method!r}"
        seq = list(getattr(ds, "DeidentificationMethodCodeSequence", []) or [])
        codes = {getattr(item, "CodeValue", None) for item in seq}
        assert "RV_DEFACE_01" in codes, f"missing RV_DEFACE_01 in {path.name}: {codes}"


def test_defacing_fallback_also_stamps_defaced_tag(tmp_path):
    """Fallback success path also stamps the defacing tag (AC-28 variant)."""
    import pydicom

    from radivault_gateway.deid.pixel.errors import PixelDeidEngineError

    class _Primary:
        engine_name = "primary"

        def deface_volume(self, volume_path, out_path):
            raise PixelDeidEngineError("ERR_PIXEL_DEFACE_FAILURE", "mock primary fail")

        def is_available(self):
            return True

        def version(self):
            return "0"

    study_dir = tmp_path / "study"
    _write_pixel_study(study_dir, burned_in="NO", modality="MR", body_part="HEAD")

    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.fallback = True
    engine = PixelDeidEngine(
        cfg,
        deface_engine=_Primary(),
        fallback_deface_engine=_FakeDefaceEngine(),
    )
    engine.process_study(
        study_dir,
        pseudo_study_uid="pseudo-tag-3",
        study_description="MR Brain",
        modality_set={"MR"},
        body_part="HEAD",
    )
    for path in sorted(study_dir.rglob("*.dcm")):
        ds = pydicom.dcmread(path, force=False)
        method = str(getattr(ds, "DeidentificationMethod", "") or "")
        assert "Defaced" in method
