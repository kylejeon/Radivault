"""De-ID engine tests — FR-6..FR-13 + Annex A matrix (AC-32)."""

from __future__ import annotations

from pathlib import Path

import pydicom
import pytest

from radivault_gateway.config import RetainOptions
from radivault_gateway.deid import DeidEngine, QuarantineRequired
from radivault_gateway.deid.engine import ANNEX_E_MATRIX
from radivault_gateway.state import StateDB


def _engine(tmp_path: Path, salt: str = "testsalt", salt_version: int = 1) -> DeidEngine:
    db = StateDB(tmp_path / "state.sqlite3")
    db.set_agent_identity(
        gateway_id="gw_t", hospital_id="h", org_root_oid="2.25.1", salt_version=salt_version
    )
    return DeidEngine(
        salt=salt,
        salt_version=salt_version,
        org_root_oid="2.25.140737488355328",
        state_db=db,
        retain=RetainOptions(),
    )


def test_basic_annex_e_strips_identifiers(make_synthetic_study, tmp_path):
    study = make_synthetic_study(n_instances=2)
    engine = _engine(tmp_path)
    result = engine.deidentify_study(study, tmp_path / "out")
    assert result.n_instances == 2
    ds = pydicom.dcmread(result.output_paths[0])
    # AC-4: PatientName, PatientID, InstitutionName, ReferringPhysicianName,
    # AccessionNumber — removed or dummy.
    assert str(ds.PatientName) == "ANON"
    assert str(ds.PatientID) != "HOSP-P-00123"
    assert "InstitutionName" not in ds
    assert str(ds.ReferringPhysicianName) == ""
    assert str(ds.AccessionNumber) == ""


def test_uid_pseudonymisation_deterministic(make_synthetic_study, tmp_path):
    study = make_synthetic_study(n_instances=1, dirname="a")
    engine = _engine(tmp_path)
    first = engine.deidentify_study(study, tmp_path / "out1")
    # Same input UID → same pseudo UID from a fresh engine reusing the DB.
    pseudo_second = engine.pseudo_uid(_read_original_study_uid(study), "study")
    assert pseudo_second == first.pseudo_study_uid


def test_patient_date_offset_consistent_across_studies(make_synthetic_study, tmp_path):
    # Two studies, same patient → same offset. (FR-10, AC-7)
    study_a = make_synthetic_study(
        n_instances=1, study_date="20260401", dirname="sa", patient_id="P-ONE"
    )
    study_b = make_synthetic_study(
        n_instances=1, study_date="20260501", dirname="sb", patient_id="P-ONE"
    )
    engine = _engine(tmp_path)
    res_a = engine.deidentify_study(study_a, tmp_path / "outa")
    res_b = engine.deidentify_study(study_b, tmp_path / "outb")
    assert res_a.patient_offset_days == res_b.patient_offset_days
    # The shifted StudyDate difference must equal the original 30-day delta.
    ds_a = pydicom.dcmread(res_a.output_paths[0])
    ds_b = pydicom.dcmread(res_b.output_paths[0])
    from datetime import datetime

    da = datetime.strptime(str(ds_a.StudyDate), "%Y%m%d").date()
    db_ = datetime.strptime(str(ds_b.StudyDate), "%Y%m%d").date()
    assert (db_ - da).days == 30


def test_different_patients_get_independent_offsets(make_synthetic_study, tmp_path):
    study_a = make_synthetic_study(n_instances=1, dirname="pa", patient_id="P-AAA")
    study_b = make_synthetic_study(n_instances=1, dirname="pb", patient_id="P-BBB")
    engine = _engine(tmp_path)
    a = engine.deidentify_study(study_a, tmp_path / "outa")
    b = engine.deidentify_study(study_b, tmp_path / "outb")
    assert a.patient_offset_days != b.patient_offset_days


def test_burned_in_triggers_quarantine(make_synthetic_study, tmp_path):
    study = make_synthetic_study(n_instances=1, burned_in="YES", dirname="burn")
    engine = _engine(tmp_path)
    with pytest.raises(QuarantineRequired) as exc:
        engine.deidentify_study(study, tmp_path / "out")
    assert exc.value.reason == "burned_in_yes"


def test_blacklist_modality_quarantine(make_synthetic_study, tmp_path):
    study = make_synthetic_study(n_instances=1, modality="SC", dirname="sc")
    engine = _engine(tmp_path)
    with pytest.raises(QuarantineRequired) as exc:
        engine.deidentify_study(study, tmp_path / "out")
    assert exc.value.reason == "blacklist_modality"


def test_reverify_passes_for_clean_output(make_synthetic_study, tmp_path):
    study = make_synthetic_study(n_instances=2)
    engine = _engine(tmp_path)
    result = engine.deidentify_study(study, tmp_path / "out")
    reverify = engine.reverify(result.output_paths[0].parent)
    assert reverify.ok is True


def test_method_tags_set(make_synthetic_study, tmp_path):
    study = make_synthetic_study(n_instances=1)
    engine = _engine(tmp_path)
    result = engine.deidentify_study(study, tmp_path / "out")
    ds = pydicom.dcmread(result.output_paths[0])
    assert ds.PatientIdentityRemoved == "YES"
    assert "RadiVault" in str(ds.DeidentificationMethod)
    assert "Annex E" in str(ds.DeidentificationMethod)
    assert len(ds.DeidentificationMethodCodeSequence) >= 1
    codes = {item.CodeValue for item in ds.DeidentificationMethodCodeSequence}
    assert "113100" in codes  # Basic profile


def test_original_uids_not_present_in_output(make_synthetic_study, tmp_path):
    study = make_synthetic_study(n_instances=1)
    engine = _engine(tmp_path)
    original_uid = _read_original_study_uid(study)
    result = engine.deidentify_study(study, tmp_path / "out")
    # AC-6: original UID must not appear in output bytes.
    for path in result.output_paths:
        body = path.read_bytes()
        assert original_uid.encode() not in body


def test_reverify_fails_when_blacklisted_tag_left(make_synthetic_study, tmp_path, monkeypatch):
    """Sanity: if a mutated engine leaves InstitutionName in place, reverify fails."""
    study = make_synthetic_study(n_instances=1)
    engine = _engine(tmp_path)
    # Patch ANNEX_E_MATRIX to K on InstitutionName for this test.
    original = dict(ANNEX_E_MATRIX)
    try:
        ANNEX_E_MATRIX[(0x0008, 0x0080)] = "K"
        result = engine.deidentify_study(study, tmp_path / "out")
        rv = engine.reverify(result.output_paths[0].parent)
        assert rv.ok is False
        offending_tags = {(g, e) for g, e, _ in rv.offending}
        assert (0x0008, 0x0080) in offending_tags
    finally:
        ANNEX_E_MATRIX.clear()
        ANNEX_E_MATRIX.update(original)


def test_annex_a_matrix_covers_required_tags():
    """AC-32: matrix must include every key tag from dev-spec §13."""
    required = [
        (0x0010, 0x0010),
        (0x0010, 0x0020),
        (0x0010, 0x0030),
        (0x0010, 0x1040),
        (0x0008, 0x0050),
        (0x0008, 0x0080),
        (0x0008, 0x0090),
        (0x0020, 0x000D),
        (0x0020, 0x000E),
        (0x0008, 0x0018),
        (0x0020, 0x0052),
        (0x0008, 0x0020),
        (0x0028, 0x0301),
    ]
    for tag in required:
        assert tag in ANNEX_E_MATRIX, f"missing matrix entry for {tag}"


def _read_original_study_uid(study_dir: Path) -> str:
    ds = pydicom.dcmread(next(study_dir.glob("*.dcm")))
    return str(ds.StudyInstanceUID)
