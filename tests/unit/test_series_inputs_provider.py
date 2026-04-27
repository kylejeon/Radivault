"""Unit tests for ``radivault_gateway.preview_provider``.

jpg-preview-defacing FR-PREVIEW-2 / round-2 closeout — round 1 shipped
``_empty_series_inputs`` as the default ``SeriesInputsProvider``. This
module replaces it with a real on-disk-staging walker. These tests
prove:

  1. Single-series CT head with BodyPartExamined=HEAD →
     SeriesInput(body_part="HEAD"), the deface gate triggers downstream
     (verified by piping the output through ``decide_deface``).
  2. Multi-series MR (HEAD + KNEE) → 2 SeriesInputs, only HEAD
     deface-gates.
  3. DICOM with no BodyPartExamined but StudyDescription="Brain MRI" →
     regex fallback gates on the description.
  4. Empty staging dir / missing study dir → returns ``[]`` cleanly.

The tests use real DICOM files written via pydicom so the provider
exercises its actual pydicom.dcmread codepath.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from radivault_gateway.preview_pipeline import decide_deface
from radivault_gateway.preview_provider import (
    _collect_series_inputs,
    gateway_series_inputs_provider,
)
from radivault_gateway.transfer.claim import Claim


def _write_dicom(
    out_path: Path,
    *,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    modality: str,
    body_part: str | None,
    study_description: str | None = None,
    series_description: str | None = None,
    protocol_name: str | None = None,
) -> Path:
    """Write a minimal DICOM under ``out_path`` (file path, not dir)."""
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    fm.MediaStorageSOPInstanceUID = sop_uid
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = "1.2.3.4"

    ds = FileDataset(
        filename_or_obj=str(out_path),
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
    if body_part is not None:
        ds.BodyPartExamined = body_part
    if study_description is not None:
        ds.StudyDescription = study_description
    if series_description is not None:
        ds.SeriesDescription = series_description
    if protocol_name is not None:
        ds.ProtocolName = protocol_name
    ds.InstanceNumber = 1

    # Tiny pixel data so the file is real — provider only reads headers
    # (stop_before_pixels=True) but a fully-formed DICOM is needed for
    # pydicom.dcmread to succeed.
    ds.Rows = 4
    ds.Columns = 4
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = np.zeros((4, 4), dtype="uint16").tobytes()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(out_path, enforce_file_format=False)
    return out_path


def _make_claim(study_uid: str) -> Claim:
    return Claim(
        transfer_job_id="tj_p2",
        order_id="ord_p2",
        hospital_id="hosp_p2",
        studies=[{"pseudo_study_uid": study_uid, "expected_instances": 1}],
        lease_expires_at="2030-01-01T00:00:00Z",
        ruleset_version_required="v0.1.0",
        salt_version_required=1,
        cancel_requested=False,
    )


# ---------------------------------------------------------------------------
# Case 1 — single-series CT head, body_part=HEAD
# ---------------------------------------------------------------------------


def test_single_series_ct_head_emits_one_input_with_deface_gate(tmp_path):
    study = "RV-STD-head1"
    series = "RV-SER-head1a"
    study_dir = tmp_path / study
    series_dir = study_dir / series
    _write_dicom(
        series_dir / f"{generate_uid()}.dcm",
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
        modality="CT",
        body_part="HEAD",
    )

    inputs = _collect_series_inputs(study_dir=study_dir)
    assert len(inputs) == 1
    s = inputs[0]
    assert s.pseudo_series_uid == series
    assert s.series_num == 1
    assert s.modality == "CT"
    assert s.body_part == "HEAD"

    decision, reason = decide_deface(
        modality=s.modality,
        body_part=s.body_part,
        study_description=None,
        protocol_name=s.protocol_name,
    )
    assert decision == "required"
    assert reason == "BodyPartExamined=HEAD"


# ---------------------------------------------------------------------------
# Case 2 — multi-series MR with HEAD + KNEE
# ---------------------------------------------------------------------------


def test_multi_series_mr_head_and_knee_only_head_gates(tmp_path):
    study = "RV-STD-multi1"
    study_dir = tmp_path / study

    head_series = study_dir / "RV-SER-head"
    _write_dicom(
        head_series / "01.dcm",
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
        modality="MR",
        body_part="HEAD",
    )

    knee_series = study_dir / "RV-SER-knee"
    _write_dicom(
        knee_series / "01.dcm",
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
        modality="MR",
        body_part="KNEE",
    )

    inputs = _collect_series_inputs(study_dir=study_dir)
    assert len(inputs) == 2
    by_uid = {s.pseudo_series_uid: s for s in inputs}
    assert "RV-SER-head" in by_uid
    assert "RV-SER-knee" in by_uid

    head = by_uid["RV-SER-head"]
    knee = by_uid["RV-SER-knee"]
    assert head.body_part == "HEAD"
    assert knee.body_part == "KNEE"

    head_decision, _ = decide_deface(
        modality=head.modality,
        body_part=head.body_part,
        study_description=None,
        protocol_name=None,
    )
    knee_decision, _ = decide_deface(
        modality=knee.modality,
        body_part=knee.body_part,
        study_description=None,
        protocol_name=None,
    )
    assert head_decision == "required"
    assert knee_decision == "not_required"

    # series_num assigned in directory-sort order; both series exist
    # contiguously [1, 2]. The exact values matter less than uniqueness.
    nums = sorted(s.series_num for s in inputs)
    assert nums == [1, 2]


# ---------------------------------------------------------------------------
# Case 3 — no BodyPartExamined but StudyDescription="Brain MRI" → regex
# ---------------------------------------------------------------------------


def test_no_body_part_with_brain_mri_study_description_regex_gates(tmp_path):
    study = "RV-STD-regex1"
    series = "RV-SER-regex1a"
    study_dir = tmp_path / study
    series_dir = study_dir / series
    _write_dicom(
        series_dir / "01.dcm",
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
        modality="MR",
        body_part=None,
        study_description="Brain MRI w/ contrast",
    )

    inputs = _collect_series_inputs(study_dir=study_dir)
    assert len(inputs) == 1
    s = inputs[0]
    assert s.body_part is None
    # StudyDescription is read off the DICOM but lives at study level —
    # the provider DOES NOT propagate it onto the SeriesInput. Instead,
    # ``with_preview_pipeline`` passes ``manifest_entry["study_description"]``
    # to ``process_study`` which forwards it. So here we verify the
    # downstream gate works when given the same description value.
    decision, reason = decide_deface(
        modality=s.modality,
        body_part=s.body_part,
        study_description="Brain MRI w/ contrast",
        protocol_name=s.protocol_name,
    )
    assert decision == "required"
    assert reason.startswith("regex:StudyDescription=")


# ---------------------------------------------------------------------------
# Case 4 — empty / missing staging dirs
# ---------------------------------------------------------------------------


def test_missing_study_dir_returns_empty(tmp_path):
    """The mock_runner / synth path doesn't actually stage DICOMs to
    disk. ``with_preview_pipeline``'s contract is that the provider
    returns ``[]`` cleanly — the wrapper then yields a preview block
    with ``series=[]`` (per FR-PREVIEW-1)."""
    inputs = _collect_series_inputs(study_dir=tmp_path / "does-not-exist")
    assert inputs == []


def test_existing_but_empty_study_dir_returns_empty(tmp_path):
    """A study dir with no series subdirs (e.g. fetch failed before
    De-ID) returns ``[]`` rather than raising."""
    study_dir = tmp_path / "empty-study"
    study_dir.mkdir()
    inputs = _collect_series_inputs(study_dir=study_dir)
    assert inputs == []


def test_series_dir_with_no_dicoms_is_skipped(tmp_path):
    """A study with one populated series and one empty series → 1
    SeriesInput. The empty one is silently skipped."""
    study_dir = tmp_path / "RV-STD-mixed"
    populated = study_dir / "RV-SER-1"
    _write_dicom(
        populated / "01.dcm",
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
        modality="CT",
        body_part="CHEST",
    )
    (study_dir / "RV-SER-empty").mkdir()

    inputs = _collect_series_inputs(study_dir=study_dir)
    assert len(inputs) == 1
    assert inputs[0].pseudo_series_uid == "RV-SER-1"


# ---------------------------------------------------------------------------
# Top-level wrapper — env-var aware
# ---------------------------------------------------------------------------


def test_top_level_wrapper_reads_staging_root_env(tmp_path, monkeypatch):
    """``gateway_series_inputs_provider`` is the public entry point
    used by the CLI; it reads ``RADIVAULT_STAGING_ROOT`` to find the
    on-disk staging dir."""
    study = "RV-STD-env1"
    study_dir = tmp_path / study
    series_dir = study_dir / "RV-SER-env1a"
    _write_dicom(
        series_dir / "01.dcm",
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
        modality="CT",
        body_part="HEAD",
    )

    monkeypatch.setenv("RADIVAULT_STAGING_ROOT", str(tmp_path))
    claim = _make_claim(study)
    manifest_entry = {"pseudo_study_uid": study}

    inputs = gateway_series_inputs_provider(
        claim=claim, manifest_entry=manifest_entry
    )
    assert len(inputs) == 1
    assert inputs[0].body_part == "HEAD"


def test_top_level_wrapper_missing_pseudo_study_uid_returns_empty():
    """Defensive — ``manifest_entry`` should always carry the UID, but
    if it doesn't (corrupt upstream), return [] rather than raising."""
    claim = _make_claim("RV-STD-x")
    inputs = gateway_series_inputs_provider(
        claim=claim, manifest_entry={"n_instances": 0}
    )
    assert inputs == []
