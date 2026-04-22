"""State DB tests."""

from __future__ import annotations

from pathlib import Path

from radivault_gateway.state import StateDB, StudyState


def test_schema_created_on_first_open(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    assert db.get_agent_identity() is None
    db.set_agent_identity(
        gateway_id="gw_a",
        hospital_id="hosp_a",
        org_root_oid="2.25.1",
        salt_version=1,
    )
    ident = db.get_agent_identity()
    assert ident is not None and ident["gateway_id"] == "gw_a"
    db.close()


def test_uid_map_idempotent(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_uid_map("1.2.3", "2.25.x", kind="study", salt_version=1)
    db.upsert_uid_map("1.2.3", "2.25.different", kind="study", salt_version=1)
    assert db.lookup_pseudo_uid("1.2.3") == "2.25.x"  # first write wins


def test_patient_offset_persisted(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_patient_offset("hashed_pid", -42, salt_version=1)
    assert db.lookup_patient_offset("hashed_pid") == -42


def test_study_job_lifecycle(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_study_job(
        "2.25.x",
        state=StudyState.QUEUED,
        modalities=["MR"],
        n_instances=10,
        n_bytes=1024,
    )
    db.mark_state("2.25.x", StudyState.DEIDED)
    db.mark_state("2.25.x", StudyState.UPLOADED)
    row = db.get_study_job("2.25.x")
    assert row is not None
    assert row["state"] == "uploaded"
    assert row["deided_at"] is not None
    assert row["uploaded_at"] is not None


def test_counts_by_state(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_study_job("a", state=StudyState.UPLOADED)
    db.upsert_study_job("b", state=StudyState.UPLOADED)
    db.upsert_study_job("c", state=StudyState.QUARANTINED)
    counts = db.counts_by_state()
    assert counts == {"uploaded": 2, "quarantined": 1}


def test_quarantine_and_retry(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    qid = db.add_quarantine("2.25.x", reason="burned_in_yes", payload_path="/q/x")
    assert qid > 0
    db.upsert_study_job("2.25.x", state=StudyState.FAILED_UPLOAD)
    db.schedule_retry("2.25.x", "2026-04-22T10:00:00Z")
    db.schedule_retry("2.25.x", "2026-04-22T10:05:00Z")
    db.clear_retry("2.25.x")
