"""Unit tests for ``radivault_gateway.thumbnail`` (FR-THUMB-1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from radivault_gateway.thumbnail import (
    SAFE_MODALITIES,
    ThumbnailResult,
    _ct_window_for_body_part,
    generate_thumbnail,
)


def test_safe_modalities_includes_ct_mr() -> None:
    assert "CT" in SAFE_MODALITIES
    assert "MR" in SAFE_MODALITIES
    assert "CR" in SAFE_MODALITIES
    assert "DR" in SAFE_MODALITIES
    assert "DX" in SAFE_MODALITIES


def test_ct_window_chest() -> None:
    center, width = _ct_window_for_body_part("CHEST")
    assert center == -600.0
    assert width == 1500.0


def test_ct_window_abdomen() -> None:
    center, width = _ct_window_for_body_part("ABDOMEN")
    assert center == 50.0
    assert width == 400.0


def test_ct_window_head() -> None:
    center, width = _ct_window_for_body_part("HEAD")
    assert center == 40.0
    assert width == 80.0


def _make_pixel_dicom(
    tmp_path: Path,
    *,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    modality: str = "CT",
    body_part: str = "CHEST",
    instance_number: int = 1,
    burned_in: str | None = None,
    rows: int = 64,
    cols: int = 64,
) -> Path:
    """Create a minimal DICOM with synthetic 16-bit pixel data."""
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
    ds.PatientID = "PID"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = sop_uid
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.Modality = modality
    ds.BodyPartExamined = body_part
    ds.InstanceNumber = instance_number
    if burned_in is not None:
        ds.BurnedInAnnotation = burned_in

    # Synthetic pixel data: a gradient so windowing has work to do.
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    # CT windowing — synthetic grayscale gradient with known dynamic range.
    px = np.tile(np.linspace(0, 4000, cols, dtype="uint16"), (rows, 1))
    ds.PixelData = px.tobytes()

    out = tmp_path / f"{sop_uid}.dcm"
    ds.save_as(out, enforce_file_format=False)
    return out


def test_thumbnail_skips_burned_in(tmp_path: Path) -> None:
    sop = generate_uid()
    path = _make_pixel_dicom(
        tmp_path,
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=sop,
        burned_in="YES",
    )
    res = generate_thumbnail([path], modality="CT", body_part="CHEST")
    assert res is None


def test_thumbnail_skips_unknown_modality(tmp_path: Path) -> None:
    sop = generate_uid()
    path = _make_pixel_dicom(
        tmp_path,
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=sop,
        modality="US",  # not in SAFE_MODALITIES
    )
    res = generate_thumbnail([path], modality="US", body_part=None)
    assert res is None


def test_thumbnail_ct_chest_passes(tmp_path: Path) -> None:
    study_uid = generate_uid()
    series_uid = generate_uid()
    paths = []
    for i in range(5):
        sop = generate_uid()
        paths.append(
            _make_pixel_dicom(
                tmp_path,
                study_uid=study_uid,
                series_uid=series_uid,
                sop_uid=sop,
                modality="CT",
                body_part="CHEST",
                instance_number=i + 1,
            )
        )
    res = generate_thumbnail(paths, modality="CT", body_part="CHEST")
    assert res is not None
    assert res.format == "JPEG"
    assert res.width <= 256
    assert res.height <= 256
    assert res.slice_count == 5
    # 5 // 2 = 2 (middle index)
    assert res.slice_index == 2
    assert len(res.bytes) > 0
    assert len(res.sha256) == 64
    assert res.phi_scrub_status == "passed"
    # JPEG SOI marker
    assert res.bytes.startswith(b"\xff\xd8\xff")


def test_thumbnail_returns_none_for_empty_input() -> None:
    res = generate_thumbnail([], modality="CT", body_part="CHEST")
    assert res is None


def test_thumbnail_sorts_by_instance_number(tmp_path: Path) -> None:
    """Out-of-order InstanceNumbers must be sorted before middle picks."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    paths = []
    # Files written in order [3, 1, 5, 2, 4] but InstanceNumber set correctly.
    for i, in_no in enumerate([3, 1, 5, 2, 4]):
        sop = generate_uid()
        paths.append(
            _make_pixel_dicom(
                tmp_path,
                study_uid=study_uid,
                series_uid=series_uid,
                sop_uid=sop,
                modality="CT",
                body_part="CHEST",
                instance_number=in_no,
            )
        )
    res = generate_thumbnail(paths, modality="CT", body_part="CHEST")
    assert res is not None
    # 5 sorted instances, middle index = 2 (which is InstanceNumber=3)
    assert res.slice_index == 2
    assert res.slice_count == 5
