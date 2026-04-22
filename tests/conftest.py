"""Shared pytest fixtures.

Synthetic DICOM files generated from scratch so we never ship or depend on
real PHI. Pydicom's ``dcmread`` accepts them because we set the minimum
file_meta.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

import pytest
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def _make_instance(
    *,
    path: Path,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    patient_id: str = "HOSP-P-00123",
    patient_name: str = "HONG^GILDONG",
    modality: str = "MR",
    study_date: str = "20260401",
    burned_in: str = "NO",
) -> None:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"  # MR Image Storage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = "2.25.999.999"

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.PatientBirthDate = "19801215"
    ds.PatientSex = "M"
    ds.PatientAge = "045Y"
    ds.PatientAddress = "Seoul, Korea"
    ds.AccessionNumber = "ACC-0001"
    ds.InstitutionName = "Seoul Med Ctr"
    ds.InstitutionAddress = "123 Street, Seoul"
    ds.ReferringPhysicianName = "Dr. Kim"
    ds.PerformingPhysicianName = "Dr. Park"
    ds.NameOfPhysiciansReadingStudy = "Dr. Lee"
    ds.OperatorsName = "Tech Han"
    ds.StudyID = "ST-01"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = sop_uid
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.StudyDate = study_date
    ds.SeriesDate = study_date
    ds.AcquisitionDate = study_date
    ds.ContentDate = study_date
    ds.StudyTime = "101530.000"
    ds.SeriesTime = "101530.000"
    ds.AcquisitionTime = "101530.000"
    ds.ContentTime = "101530.000"
    ds.StudyDescription = "MR BRAIN W/O CONTRAST secret_note"
    ds.SeriesDescription = "Axial T1 secret_note"
    ds.ImageComments = "comment with PHI"
    ds.StudyComments = "study comment"
    ds.Manufacturer = "ACME"
    ds.ManufacturerModelName = "Scanner3000"
    ds.DeviceSerialNumber = "SN-1234567"
    ds.StationName = "STATION-A"
    ds.Modality = modality
    ds.BurnedInAnnotation = burned_in
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    # Add a tiny private tag which should be removed.
    ds.add_new((0x0033, 0x0010), "LO", "RADIVAULT_TEST_PRIVATE")

    path.parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(path, enforce_file_format=False)


@pytest.fixture
def make_synthetic_study(tmp_path: Path):
    """Factory fixture: build a study directory with N .dcm instances."""

    def _build(
        *,
        n_instances: int = 3,
        patient_id: str = "HOSP-P-00123",
        patient_name: str = "HONG^GILDONG",
        modality: str = "MR",
        study_date: str = "20260401",
        burned_in: str = "NO",
        dirname: str = "study",
    ) -> Path:
        study_dir = tmp_path / dirname
        study_uid = f"1.2.840.{abs(hash(dirname)) % 10**10}.{int(date.today().toordinal())}"
        series_uid = f"{study_uid}.1"
        for i in range(n_instances):
            sop_uid = f"{series_uid}.{i + 1}"
            _make_instance(
                path=study_dir / f"inst_{i + 1:04d}.dcm",
                study_uid=study_uid,
                series_uid=series_uid,
                sop_uid=sop_uid,
                patient_id=patient_id,
                patient_name=patient_name,
                modality=modality,
                study_date=study_date,
                burned_in=burned_in,
            )
        return study_dir

    return _build


@pytest.fixture
def tmp_salt() -> str:
    return "testsalt_" + os.urandom(8).hex()
