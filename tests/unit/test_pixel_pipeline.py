"""PixelDeidEngine orchestrator tests with mocked OCR + defacing engines.

Covers triage routing, OCR redaction, re-verification, medical exclusion,
and defacing success/fallback paths. Heavy pydicom pixel manipulation is
covered via synthetic 8x8 frames that the synthesized ``make_synthetic_study``
fixture augments with pixel data.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from radivault_gateway.deid.pixel import (
    OcrBox,
    PixelDeidConfig,
    PixelDeidEngine,
    PixelQuarantineRequired,
    TriageDecision,
)
from radivault_gateway.deid.pixel.deface_engine import DefaceResult
from radivault_gateway.deid.pixel.errors import PixelDeidEngineError

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy not installed (pixel extras absent)",
)


def _study_with_pixels(
    tmp_path: Path,
    *,
    modality: str = "US",
    burned_in: str = "YES",
    body_part: str = "",
    study_description: str = "US pelvic",
):
    """Create a minimal DICOM with valid pixel data for the pixel pipeline."""
    import numpy as np
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    study_dir = tmp_path / "study"
    study_dir.mkdir()
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"  # SC
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    path = study_dir / "inst_0001.dcm"
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "ANON"
    ds.PatientID = "ANON"
    ds.StudyInstanceUID = "1.2.840.pseudo"
    ds.SeriesInstanceUID = "1.2.840.pseudo.1"
    ds.SOPInstanceUID = "1.2.3.4.5"
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.Modality = modality
    ds.BurnedInAnnotation = burned_in
    ds.StudyDescription = study_description
    if body_part:
        ds.BodyPartExamined = body_part
    # Pixel data - 16x16 uint16 filled with 200.
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
    return study_dir


class _FakeOcrEngine:
    engine_name = "fake_ocr"

    def __init__(self, boxes: list[OcrBox], residual_boxes: list[OcrBox] | None = None):
        self._boxes = boxes
        self._residual = residual_boxes or []
        self._call_count = 0

    def detect_text(self, image, *, languages):
        self._call_count += 1
        # First call: full frame detection. Subsequent calls: residual recheck.
        if self._call_count == 1:
            return list(self._boxes)
        return list(self._residual)

    def version(self) -> str:
        return "fake-1.0"


class _FakeDefaceEngine:
    engine_name = "fake_deface"

    def __init__(self, ratio: float = 0.30, raises: bool = False):
        self._ratio = ratio
        self._raises = raises

    def deface_volume(self, volume_path, out_path) -> DefaceResult:
        if self._raises:
            raise PixelDeidEngineError("ERR_PIXEL_DEFACE_FAILURE", "mock failure")
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


def test_skip_when_no_burn_in_and_modality_not_in_allowlist(tmp_path):
    cfg = PixelDeidConfig(enabled=True)
    ocr = _FakeOcrEngine(boxes=[])
    engine = PixelDeidEngine(cfg, ocr_engine=ocr)
    study_dir = _study_with_pixels(tmp_path, modality="CT", burned_in="NO")
    triage = engine.triage(study_dir)
    assert triage.decision == TriageDecision.SKIP


def test_ocr_redacts_bbox_when_confidence_high(tmp_path):
    """AC-5 variant: engine redacts high-conf bbox."""
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.residual_recheck = False
    boxes = [OcrBox(x=2, y=2, w=6, h=4, text="PATIENT_NAME", confidence=0.9)]
    ocr = _FakeOcrEngine(boxes=boxes)
    engine = PixelDeidEngine(cfg, ocr_engine=ocr)
    study_dir = _study_with_pixels(tmp_path, modality="US", burned_in="YES")
    result = engine.process_study(
        study_dir,
        pseudo_study_uid="pseudo-1",
        study_description="US pelvic",
        modality_set={"US"},
        body_part=None,
    )
    assert result.ocr_applied is True
    assert result.n_boxes_redacted == 1
    assert result.library_ocr == "fake_ocr"


def test_ocr_residual_detection_quarantines(tmp_path):
    """AC-6 fail case: residual text after redaction → ERR_PIXEL_RESIDUAL_TEXT."""
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.residual_recheck = True
    boxes = [OcrBox(x=2, y=2, w=6, h=4, text="leak", confidence=0.9)]
    residuals = [OcrBox(x=0, y=0, w=4, h=4, text="still_there", confidence=0.93)]
    ocr = _FakeOcrEngine(boxes=boxes, residual_boxes=residuals)
    engine = PixelDeidEngine(cfg, ocr_engine=ocr)
    study_dir = _study_with_pixels(tmp_path, modality="US", burned_in="YES")
    with pytest.raises(PixelQuarantineRequired) as exc:
        engine.process_study(
            study_dir,
            pseudo_study_uid="pseudo-2",
            study_description="US pelvic",
            modality_set={"US"},
            body_part=None,
        )
    assert exc.value.code == "ERR_PIXEL_RESIDUAL_TEXT"


def test_no_box_above_threshold_quarantines(tmp_path):
    """AC-7 variant: OCR_REQUIRED but no box clears threshold → low-confidence quarantine."""
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.confidence_threshold = 0.8
    boxes = [OcrBox(x=0, y=0, w=4, h=4, text="x", confidence=0.4)]
    ocr = _FakeOcrEngine(boxes=boxes)
    engine = PixelDeidEngine(cfg, ocr_engine=ocr)
    study_dir = _study_with_pixels(tmp_path, modality="US", burned_in="YES")
    with pytest.raises(PixelQuarantineRequired) as exc:
        engine.process_study(
            study_dir,
            pseudo_study_uid="pseudo-3",
            study_description="US pelvic",
            modality_set={"US"},
            body_part=None,
        )
    assert exc.value.code == "ERR_PIXEL_OCR_LOW_CONFIDENCE"


def test_medical_exclusion_quarantines_before_defacing(tmp_path):
    """AC-10: dental StudyDescription → medical exclusion → quarantine."""
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False  # skip OCR path for clarity
    engine = PixelDeidEngine(
        cfg,
        ocr_engine=None,
        deface_engine=_FakeDefaceEngine(),
    )
    study_dir = _study_with_pixels(
        tmp_path,
        modality="CT",
        burned_in="NO",
        body_part="HEAD",
        study_description="Dental CBCT maxilla",
    )
    with pytest.raises(PixelQuarantineRequired) as exc:
        engine.process_study(
            study_dir,
            pseudo_study_uid="pseudo-4",
            study_description="Dental CBCT maxilla",
            modality_set={"CT"},
            body_part="HEAD",
        )
    assert exc.value.code == "ERR_PIXEL_MEDICAL_EXCLUSION"


def test_residual_face_voxels_quarantines(tmp_path):
    """AC-13: removed_voxel_ratio below threshold → ERR_PIXEL_RESIDUAL_FACE_VOXELS."""
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.min_removed_ratio = 0.10
    engine = PixelDeidEngine(
        cfg,
        deface_engine=_FakeDefaceEngine(ratio=0.02),
    )
    study_dir = _study_with_pixels(
        tmp_path,
        modality="MR",
        burned_in="NO",
        body_part="HEAD",
        study_description="Brain MRI",
    )
    with pytest.raises(PixelQuarantineRequired) as exc:
        engine.process_study(
            study_dir,
            pseudo_study_uid="pseudo-5",
            study_description="Brain MRI",
            modality_set={"MR"},
            body_part="HEAD",
        )
    assert exc.value.code == "ERR_PIXEL_RESIDUAL_FACE_VOXELS"


def test_defacing_fallback_used_on_primary_failure(tmp_path):
    """AC-14: pydeface failure triggers mridefacer fallback and succeeds."""
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    cfg.defacing.fallback = True
    primary = _FakeDefaceEngine(raises=True)
    fallback = _FakeDefaceEngine(ratio=0.25)
    engine = PixelDeidEngine(
        cfg,
        deface_engine=primary,
        fallback_deface_engine=fallback,
    )
    study_dir = _study_with_pixels(
        tmp_path,
        modality="MR",
        burned_in="NO",
        body_part="BRAIN",
    )
    result = engine.process_study(
        study_dir,
        pseudo_study_uid="pseudo-6",
        study_description="Brain MRI",
        modality_set={"MR"},
        body_part="BRAIN",
    )
    assert result.defacing_applied is True
    assert result.library_deface == "fake_deface"
    assert result.removed_voxel_ratio == pytest.approx(0.25)


def test_exclusion_pattern_only_skips_when_defacing_eligible(tmp_path):
    """Dental CT without HEAD body part → no defacing eligibility, no exclusion raise.

    The matcher still flags exclusion_matched=True, but the engine does not
    raise PixelQuarantineRequired because defacing was never eligible in the
    first place (modality x body_part gate fails upstream).
    """
    cfg = PixelDeidConfig(enabled=True)
    cfg.ocr.enabled = False
    engine = PixelDeidEngine(
        cfg,
        deface_engine=_FakeDefaceEngine(),
    )
    study_dir = _study_with_pixels(
        tmp_path,
        modality="CT",
        burned_in="NO",
        study_description="Dental CBCT",
    )
    # body_part=None → defacing not eligible → no exclusion firing.
    result = engine.process_study(
        study_dir,
        pseudo_study_uid="pseudo-7",
        study_description="Dental CBCT",
        modality_set={"CT"},
        body_part=None,
    )
    # Matcher saw the pattern, but no quarantine required since defacing was
    # not eligible → the engine returned normally (result object exists).
    assert result.defacing_applied is False


def test_build_pixel_deid_engine_returns_none_when_disabled():
    from radivault_gateway.deid.pixel import build_pixel_deid_engine

    cfg = PixelDeidConfig(enabled=False)
    assert build_pixel_deid_engine(cfg) is None


def test_box_hash_not_reversible():
    """FR-38: box_hash never leaks plaintext."""
    from radivault_gateway.deid.pixel import box_hash

    h = box_hash("very secret")
    assert "very secret" not in h
    assert h.startswith("sha256:") and len(h) == 7 + 16
