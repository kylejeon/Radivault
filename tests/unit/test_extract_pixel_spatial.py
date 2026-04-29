"""Unit tests for ``radivault_gateway.extract`` Tier-1 pixel/spatial fields.

dev-spec-pixel-spatial-fields FR-PSF-2 / AC-PSF-1.x.

Covers:
  - CT happy path (PixelSpacing + Rows/Columns + bits + photometric +
    FrameOfReferenceUID).
  - MR happy path (different bits + photometric, no KVP).
  - CR fallback to ImagerPixelSpacing (0018,1164) when PixelSpacing
    (0028,0030) is absent.
  - US YBR_FULL photometric carries through; modality-irrelevant
    fields (slice_thickness) collapse to None.
  - Invalid combos: rows=0, bits_stored > bits_allocated (FR-PSF-2.7).
"""

from __future__ import annotations

from pathlib import Path

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from radivault_gateway.extract import extract_study_metadata


def _make_dicom(
    tmp_path: Path,
    *,
    study_uid: str | None = None,
    series_uid: str | None = None,
    sop_uid: str | None = None,
    modality: str = "CT",
    body_part: str = "CHEST",
    pixel_spacing: tuple[float, float] | None = (0.7031, 0.7031),
    imager_pixel_spacing: tuple[float, float] | None = None,
    rows: int | None = 512,
    columns: int | None = 512,
    bits_allocated: int | None = 16,
    bits_stored: int | None = 12,
    photometric: str | None = "MONOCHROME2",
    frame_of_ref_uid: str | None = "1.2.840.test.frame.001",
    slice_thickness: float | None = 0.625,
    kvp: float | None = 120.0,
) -> Path:
    """Synthesize a minimal DICOM file with Tier-1 fields populated."""
    study_uid = study_uid or generate_uid()
    series_uid = series_uid or generate_uid()
    sop_uid = sop_uid or generate_uid()

    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    fm.MediaStorageSOPInstanceUID = sop_uid
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = "1.2.3.4"

    ds = FileDataset(
        filename_or_obj=str(tmp_path / f"{sop_uid}.dcm"),
        dataset={},
        file_meta=fm,
        preamble=b"\0" * 128,
    )
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    ds.PatientName = "ANON"
    ds.PatientID = "PID-001"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = sop_uid
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.StudyDate = "20240315"
    ds.Modality = modality
    ds.BodyPartExamined = body_part
    ds.Manufacturer = "GE"
    ds.ManufacturerModelName = "Test"
    if pixel_spacing is not None:
        ds.PixelSpacing = list(pixel_spacing)
    if imager_pixel_spacing is not None:
        ds.ImagerPixelSpacing = list(imager_pixel_spacing)
    if rows is not None:
        ds.Rows = rows
    if columns is not None:
        ds.Columns = columns
    if bits_allocated is not None:
        ds.BitsAllocated = bits_allocated
    if bits_stored is not None:
        ds.BitsStored = bits_stored
    if photometric is not None:
        ds.PhotometricInterpretation = photometric
    if frame_of_ref_uid is not None:
        ds.FrameOfReferenceUID = frame_of_ref_uid
    if slice_thickness is not None:
        ds.SliceThickness = slice_thickness
    if kvp is not None:
        ds.KVP = kvp

    out = tmp_path / f"{sop_uid}.dcm"
    ds.save_as(out, enforce_file_format=False)
    return out


# ---------------------------------------------------------------------------
# AC-PSF-1.1 — CT happy path
# ---------------------------------------------------------------------------


def test_ct_tier1_all_fields(tmp_path: Path) -> None:
    path = _make_dicom(tmp_path)
    md = extract_study_metadata([path])
    assert len(md.series) == 1
    s = md.series[0]
    assert s["photometric_interpretation"] == "MONOCHROME2"
    assert s["pixel_spacing_x"] == 0.7031
    assert s["pixel_spacing_y"] == 0.7031
    assert s["rows"] == 512
    assert s["columns"] == 512
    assert s["bits_allocated"] == 16
    assert s["bits_stored"] == 12
    assert s["frame_of_reference_uid_pseudo"] == "1.2.840.test.frame.001"
    assert s["slice_thickness_mm"] == 0.625
    assert s["kvp"] == 120.0


# ---------------------------------------------------------------------------
# AC-PSF-1.2 — MR fixture (8-bit MONOCHROME2; no KVP)
# ---------------------------------------------------------------------------


def test_mr_tier1_fields(tmp_path: Path) -> None:
    path = _make_dicom(
        tmp_path,
        modality="MR",
        kvp=None,
        slice_thickness=4.0,
        bits_allocated=8,
        bits_stored=8,
        rows=256,
        columns=256,
        pixel_spacing=(0.9375, 0.9375),
    )
    md = extract_study_metadata([path])
    s = md.series[0]
    assert s["photometric_interpretation"] == "MONOCHROME2"
    assert s["pixel_spacing_x"] == 0.9375
    assert s["pixel_spacing_y"] == 0.9375
    assert s["rows"] == 256
    assert s["columns"] == 256
    assert s["bits_allocated"] == 8
    assert s["bits_stored"] == 8
    assert s["kvp"] is None  # MR-only fixture has no KVP
    assert s["slice_thickness_mm"] == 4.0


# ---------------------------------------------------------------------------
# AC-PSF-1.3 — CR ImagerPixelSpacing fallback
# ---------------------------------------------------------------------------


def test_cr_imager_pixel_spacing_fallback(tmp_path: Path) -> None:
    path = _make_dicom(
        tmp_path,
        modality="CR",
        pixel_spacing=None,  # not present
        imager_pixel_spacing=(0.143, 0.143),  # fallback
        slice_thickness=None,
        kvp=70.0,
        bits_allocated=16,
        bits_stored=14,
        photometric="MONOCHROME2",
        frame_of_ref_uid=None,  # CR rarely has FrameOfReferenceUID
    )
    md = extract_study_metadata([path])
    s = md.series[0]
    # FR-PSF-2.2 — fallback path picks up ImagerPixelSpacing.
    assert s["pixel_spacing_x"] == 0.143
    assert s["pixel_spacing_y"] == 0.143
    assert s["slice_thickness_mm"] is None
    assert s["frame_of_reference_uid_pseudo"] is None
    # CR is not CT/MR, so md.kvp (study-level) stays None. The series-
    # level kvp dict slot is populated by extract regardless.
    assert s["kvp"] == 70.0


# ---------------------------------------------------------------------------
# AC-PSF-1.4 — US YBR_FULL — photometric carries through
# ---------------------------------------------------------------------------


def test_us_ybr_full_no_slice_thickness(tmp_path: Path) -> None:
    path = _make_dicom(
        tmp_path,
        modality="US",
        photometric="YBR_FULL_422",
        pixel_spacing=None,
        imager_pixel_spacing=None,
        slice_thickness=None,
        kvp=None,
        bits_allocated=8,
        bits_stored=8,
        rows=480,
        columns=640,
        frame_of_ref_uid=None,
    )
    md = extract_study_metadata([path])
    s = md.series[0]
    assert s["photometric_interpretation"] == "YBR_FULL_422"
    assert s["slice_thickness_mm"] is None
    assert s["pixel_spacing_x"] is None
    assert s["pixel_spacing_y"] is None
    assert s["rows"] == 480
    assert s["columns"] == 640


# ---------------------------------------------------------------------------
# AC-PSF-1.5 — invalid combos collapse to None (FR-PSF-2.7)
# ---------------------------------------------------------------------------


def test_invalid_rows_zero(tmp_path: Path) -> None:
    """Rows=0 is a malformed DICOM; collapse to None rather than store 0."""
    path = _make_dicom(tmp_path, rows=0)
    md = extract_study_metadata([path])
    s = md.series[0]
    assert s["rows"] is None
    # other fields untouched
    assert s["columns"] == 512


def test_invalid_bits_stored_exceeds_allocated(tmp_path: Path) -> None:
    """bits_stored > bits_allocated is invalid; both collapse to None."""
    path = _make_dicom(tmp_path, bits_allocated=8, bits_stored=12)
    md = extract_study_metadata([path])
    s = md.series[0]
    assert s["bits_allocated"] is None
    assert s["bits_stored"] is None


def test_invalid_pixel_spacing_negative(tmp_path: Path) -> None:
    """Negative pixel spacing collapses to None."""
    path = _make_dicom(tmp_path, pixel_spacing=(-1.0, 0.7))
    md = extract_study_metadata([path])
    s = md.series[0]
    # _parse_float drops <=0 values; second element OK.
    assert s["pixel_spacing_x"] is None
    assert s["pixel_spacing_y"] == 0.7


# ---------------------------------------------------------------------------
# Manifest version + wire-shape sanity
# ---------------------------------------------------------------------------


def test_build_manifest_v3_when_tier1_present(tmp_path: Path) -> None:
    """FR-PSF-3.1 — manifest_version bumps to 3 when any Tier-1 series field
    is populated."""
    from radivault_gateway.upload.client import UploadClient

    dcm = _make_dicom(tmp_path)
    md = extract_study_metadata([dcm])
    client = UploadClient.__new__(UploadClient)
    # build_manifest is a pure method — no _client / I/O needed.
    manifest = UploadClient.build_manifest(
        client,
        gateway_id="gw-test",
        hospital_id="hosp-test",
        pseudo_study_uid="study-123",
        modalities=["CT"],
        ruleset_version="r1",
        salt_version=1,
        method_codes=["RV-A"],
        dcm_files=[dcm],
        study_metadata=md,
    )
    assert manifest["manifest_version"] == 3
    series = manifest["series"]
    assert series and series[0]["photometric_interpretation"] == "MONOCHROME2"
    assert series[0]["pixel_spacing_x"] == 0.7031
    assert series[0]["rows"] == 512
    assert series[0]["bits_stored"] == 12
    assert series[0]["frame_of_reference_uid_pseudo"] == "1.2.840.test.frame.001"


def test_build_manifest_v2_when_no_tier1(tmp_path: Path) -> None:
    """FR-PSF-3.5 — gateways that never populate Tier-1 stay at v2."""
    from radivault_gateway.upload.client import UploadClient

    dcm = _make_dicom(
        tmp_path,
        photometric=None,
        pixel_spacing=None,
        imager_pixel_spacing=None,
        rows=None,
        columns=None,
        bits_allocated=None,
        bits_stored=None,
        frame_of_ref_uid=None,
    )
    md = extract_study_metadata([dcm])
    client = UploadClient.__new__(UploadClient)
    manifest = UploadClient.build_manifest(
        client,
        gateway_id="gw-test",
        hospital_id="hosp-test",
        pseudo_study_uid="study-456",
        modalities=["CT"],
        ruleset_version="r1",
        salt_version=1,
        method_codes=["RV-A"],
        dcm_files=[dcm],
        study_metadata=md,
    )
    # No Tier-1 series fields populated -> v2 wire shape.
    assert manifest["manifest_version"] == 2
