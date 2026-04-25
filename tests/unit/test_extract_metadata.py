"""Unit tests for ``radivault_gateway.extract`` (FR-META-2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from radivault_gateway.extract import (
    StudyMetadata,
    _parse_age_bucket,
    _parse_birthdate_age,
    _parse_body_part,
    _parse_sex,
    _parse_study_date,
    _trim,
    extract_study_metadata,
)


# ---------- pure-function units (no I/O) ----------


def test_age_bucket_basic() -> None:
    assert _parse_age_bucket("030Y") == "30-34"
    assert _parse_age_bucket("034Y") == "30-34"
    assert _parse_age_bucket("055Y") == "55-59"
    assert _parse_age_bucket("089Y") == "85-89"


def test_age_bucket_90plus() -> None:
    assert _parse_age_bucket("090Y") == "90+"
    assert _parse_age_bucket("095Y") == "90+"


def test_age_bucket_invalid() -> None:
    assert _parse_age_bucket(None) is None
    assert _parse_age_bucket("") is None
    assert _parse_age_bucket("030D") is None  # neonatal day-units
    assert _parse_age_bucket("xxx") is None


def test_birthdate_age_fallback() -> None:
    # 1955-03-15 birth, 2024-03-20 study → 69
    assert _parse_birthdate_age("19550315", "20240320") == "65-69"


def test_sex_parsing() -> None:
    assert _parse_sex("M") == "M"
    assert _parse_sex("f") == "F"
    assert _parse_sex("O") == "O"
    assert _parse_sex("U") is None
    assert _parse_sex("") is None
    assert _parse_sex(None) is None


def test_body_part_normalize() -> None:
    assert _parse_body_part("chest") == "CHEST"
    assert _parse_body_part("  Abdomen  ") == "ABDOMEN"
    assert _parse_body_part("") is None
    assert _parse_body_part(None) is None


def test_trim() -> None:
    assert _trim("a" * 70, 64) == "a" * 64
    assert _trim("  hello  ", 10) == "hello"
    assert _trim("", 10) is None


def test_study_date() -> None:
    assert _parse_study_date("20240315") == date(2024, 3, 15)
    assert _parse_study_date("2024-03-15") == date(2024, 3, 15)
    assert _parse_study_date(None) is None
    assert _parse_study_date("nope") is None


# ---------- DICOM-driven extract_study_metadata ----------


def _make_dicom(
    tmp_path: Path,
    *,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    instance_number: int = 1,
    modality: str = "CT",
    body_part: str = "CHEST",
    manufacturer: str = "GE Medical Systems",
    model: str = "Revolution CT",
    sex: str = "M",
    age: str = "055Y",
    study_date: str = "20240315",
    slice_thickness: float | None = 1.25,
    kvp: float | None = 120.0,
) -> Path:
    """Synthesize a tiny DICOM file with the v2 metadata fields populated."""
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
    ds.PatientSex = sex
    ds.PatientAge = age
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = sop_uid
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.StudyDate = study_date
    ds.Modality = modality
    ds.BodyPartExamined = body_part
    ds.Manufacturer = manufacturer
    ds.ManufacturerModelName = model
    ds.InstanceNumber = instance_number
    if slice_thickness is not None:
        ds.SliceThickness = slice_thickness
    if kvp is not None:
        ds.KVP = kvp

    out = tmp_path / f"{sop_uid}.dcm"
    ds.save_as(out, enforce_file_format=False)
    return out


def test_extract_ct_study(tmp_path: Path) -> None:
    study_uid = generate_uid()
    series_uid = generate_uid()
    paths = []
    for i in range(3):
        sop = generate_uid()
        paths.append(
            _make_dicom(
                tmp_path,
                study_uid=study_uid,
                series_uid=series_uid,
                sop_uid=sop,
                instance_number=i + 1,
            )
        )
    md: StudyMetadata = extract_study_metadata(paths)
    assert md.body_part_examined == "CHEST"
    assert md.manufacturer == "GE Medical Systems"
    assert md.manufacturer_model_name == "Revolution CT"
    assert md.patient_sex == "M"
    assert md.patient_age_bucket == "55-59"
    assert md.study_date_shifted == date(2024, 3, 15)
    assert md.study_year == 2024
    assert md.n_series == 1
    assert md.n_instances == 3
    assert md.total_bytes > 0
    assert md.slice_thickness_mm == 1.25
    assert md.kvp == 120.0
    # series array shape
    assert len(md.series) == 1
    assert md.series[0]["modality"] == "CT"
    assert md.series[0]["n_instances"] == 3


def test_extract_mr_no_kvp(tmp_path: Path) -> None:
    sop = generate_uid()
    path = _make_dicom(
        tmp_path,
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=sop,
        modality="MR",
        kvp=None,  # MR shouldn't have KVP
        slice_thickness=4.0,
    )
    md = extract_study_metadata([path])
    assert md.kvp is None
    assert md.slice_thickness_mm == 4.0


def test_extract_cr_no_slice_thickness(tmp_path: Path) -> None:
    sop = generate_uid()
    path = _make_dicom(
        tmp_path,
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=sop,
        modality="CR",
        slice_thickness=None,
        kvp=None,
        body_part="CHEST",
    )
    md = extract_study_metadata([path])
    # CR is not CT/MR — slice_thickness_mm and kvp should be None.
    assert md.slice_thickness_mm is None
    assert md.kvp is None


def test_extract_empty_inputs() -> None:
    md = extract_study_metadata([])
    assert md.body_part_examined is None
    assert md.n_series == 0
    assert md.n_instances == 0


def test_extract_handles_unreadable_path(tmp_path: Path) -> None:
    """A non-DICOM path in the list should be skipped, not raise."""
    valid = _make_dicom(
        tmp_path,
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
    )
    bad = tmp_path / "notdicom.dcm"
    bad.write_text("hello")
    md = extract_study_metadata([bad, valid])
    assert md.n_instances == 1
    assert md.body_part_examined == "CHEST"
