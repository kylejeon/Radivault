"""F-3 (H-1, AC-18, FR-36) — startup crash recovery for pixel_processing state.

Simulates a crash mid-pixel-stage by seeding a ``study_job`` row in the
``pixel_processing`` state and then invoking the startup recovery helper.
Asserts the row is rolled back to ``deided`` with last_error set, a
``pixel_audit_event`` with op=recovery is written, and the audit log
receives a ``pixel.recovery.applied`` hash-chained event.
"""

from __future__ import annotations

from pathlib import Path

from radivault_gateway.audit import AuditLogger
from radivault_gateway.orchestrator.recovery import recover_orphaned_pixel_processing
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB, StudyState


def _seed_orphaned_pixel_processing(db: StateDB, pseudo_uid: str) -> None:
    db.upsert_study_job(
        pseudo_uid,
        state=StudyState.DEIDED,
        modalities=["US"],
    )
    db.mark_state(pseudo_uid, StudyState.PIXEL_PROCESSING)


def test_recovery_rolls_back_orphaned_pixel_processing(tmp_path):
    db = StateDB(tmp_path / "state.sqlite3")
    db.set_agent_identity(gateway_id="gw_t", hospital_id="h", org_root_oid="2.25.1", salt_version=1)
    staging = StagingManager(tmp_path / "stg")
    audit = AuditLogger(tmp_path / "audit.log", gateway_id="gw_t")
    pseudo_uid = "2.25.1.PIXEL.RECOVER.1"
    _seed_orphaned_pixel_processing(db, pseudo_uid)
    # Simulate a partial staging directory from the crashed run.
    (Path(staging.root) / pseudo_uid).mkdir(parents=True, exist_ok=True)

    result = recover_orphaned_pixel_processing(db, audit=audit, staging=staging)

    assert result.recovered == 1
    assert result.pseudo_study_uids == [pseudo_uid]

    job = db.get_study_job(pseudo_uid)
    assert job is not None
    assert job["state"] == StudyState.DEIDED.value
    assert job["last_error"] == "startup_crash_recovery"

    # Partial staging artefacts removed.
    assert not (Path(staging.root) / pseudo_uid).exists()

    # pixel_audit_event row inserted with op=recovery.
    events = db.list_pixel_audit_events(pseudo_study_uid=pseudo_uid)
    assert any(e["op"] == "recovery" and e["reason"] == "startup_crash_recovery" for e in events)

    # Audit log line written.
    audit_lines = Path(tmp_path / "audit.log").read_text().splitlines()
    assert any("pixel.recovery.applied" in line for line in audit_lines)


def test_recovery_noop_when_no_orphans(tmp_path):
    db = StateDB(tmp_path / "state.sqlite3")
    db.set_agent_identity(gateway_id="gw_t", hospital_id="h", org_root_oid="2.25.1", salt_version=1)
    staging = StagingManager(tmp_path / "stg")
    audit = AuditLogger(tmp_path / "audit.log", gateway_id="gw_t")
    result = recover_orphaned_pixel_processing(db, audit=audit, staging=staging)
    assert result.recovered == 0
    assert result.pseudo_study_uids == []
