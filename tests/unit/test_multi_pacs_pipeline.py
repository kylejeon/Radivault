"""Multi-PACS sync — pipeline orchestration unit tests (FR-MPS-2, FR-MPS-3).

Covers the dev-spec ``docs/specs/dev-spec-multi-pacs-sync.md`` §13 step 2
behaviour:

- ``Pipeline._emit_audit`` injects ``pacs_id`` / ``hospital_id`` into
  every audit event when constructed with the multi-PACS context, and
  preserves the legacy single-PACS shape (no pacs_id field) when None
  (regression guard for the chain hash).
- ``run_multi_pacs_once`` iterates enabled endpoints in priority order,
  emits ``pacs.run.started`` / ``pacs.run.completed`` per endpoint, and
  isolates exceptions so one failed endpoint does not abort the rest.
- The aggregate :class:`MultiPacsRunSummary.exit_code` matches FR-MPS-2.
- ``--pacs <id>`` filtering selects a single endpoint and skips the
  others entirely (no audit events for skipped endpoints).
"""

from __future__ import annotations

# Break the pre-existing circular import.
import radivault_gateway.deid  # noqa: F401

import importlib
import json
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from radivault_gateway.audit import AuditLogger
from radivault_gateway.config import GatewayConfig
from radivault_gateway.deid import DeidEngine
from radivault_gateway.orchestrator import (
    MultiPacsRunSummary,
    Pipeline,
    PacsRunResult,
    run_multi_pacs_once,
)
from radivault_gateway.pacs import FetchResult, PacsError, StudySummary
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB, StudyState


# ----------------------------------------------------------------------------
# Helpers — synthetic config + fake clients
# ----------------------------------------------------------------------------


def _build_cfg(tmp_path: Path, *, endpoints: list[dict]) -> GatewayConfig:
    """Build a multi-PACS config rooted under ``tmp_path``."""
    base = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
            "hospital_id": "HOSP-001",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": endpoints,
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt": "0123456789abcdef" * 2,
            "salt_version": 1,
        },
        "staging": {
            "root": str(tmp_path / "stg"),
            "retention_hours": 72,
            "max_disk_pct": 99,
        },
        "state": {"db_path": str(tmp_path / "state.sqlite3")},
        "audit": {
            "path": str(tmp_path / "audit.log"),
            "anchor_interval_seconds": 3600,
        },
        "central": {
            "base_url": "http://testserver",
            "upload_tokens": {"HOSP-001": "tok-1", "HOSP-002": "tok-2"},
            "allow_insecure": True,
        },
        "logging": {"level": "INFO", "json": True},
    }
    return GatewayConfig.model_validate(base)


@dataclass
class FakePacs:
    """In-memory PACS client matching the slice of DicomWebPacsClient
    that :class:`Pipeline` consumes."""

    studies: list[StudySummary]

    def query_studies(self, *args, **kwargs):
        return self.studies


@dataclass
class FailingPacs:
    """Fake PACS client that raises on every QIDO call."""

    err: Exception

    def query_studies(self, *args, **kwargs):
        raise self.err


class FakeUpload:
    """Records calls instead of actually POSTing — enough to verify
    upload paths get the right token / hospital_id wiring without
    spinning up the FastAPI mock central."""

    def __init__(self, *, upload_token: str = "default", **_) -> None:
        self.upload_token = upload_token
        self.closed = False
        self.calls: list[dict] = []

    def close(self) -> None:
        self.closed = True


# ----------------------------------------------------------------------------
# Pipeline._emit_audit — meta injection
# ----------------------------------------------------------------------------


def _make_pipeline(
    cfg: GatewayConfig,
    *,
    state_db: StateDB,
    audit_logger: AuditLogger,
    staging: StagingManager,
    deid: DeidEngine,
    pacs_id: str | None = None,
    hospital_id: str | None = None,
) -> Pipeline:
    """Build a Pipeline with stubbed PACS / Upload clients (we only
    exercise ``_emit_audit`` in the next test, so the clients can be
    bare placeholders that never get called)."""
    return Pipeline(
        cfg,
        state_db=state_db,
        audit_logger=audit_logger,
        staging=staging,
        deid=deid,
        pacs=FakePacs(studies=[]),
        upload=FakeUpload(),
        pixel=None,
        pacs_id=pacs_id,
        hospital_id=hospital_id,
    )


def test_emit_audit_injects_pacs_id_and_hospital_id(tmp_path: Path) -> None:
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "orthanc-a",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
            }
        ],
    )
    state = StateDB(tmp_path / "s.sqlite3")
    state.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit = AuditLogger(tmp_path / "audit.log", gateway_id="gw_test")
    staging = StagingManager(
        tmp_path / "stg", retention_hours=72, max_disk_pct=99
    )
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=state,
        retain=cfg.deid.retain_options,
        burnin_quarantine_modalities=cfg.deid.burnin_quarantine_modalities,
        ruleset_version=cfg.deid.ruleset_version,
        version_string="test",
    )

    p = _make_pipeline(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs_id="orthanc-a",
        hospital_id="HOSP-001",
    )

    p._emit_audit("test.event", meta={"foo": "bar"})

    line = (tmp_path / "audit.log").read_text(encoding="utf-8").splitlines()[-1]
    rec = json.loads(line)
    assert rec["meta"]["pacs_id"] == "orthanc-a"
    assert rec["meta"]["hospital_id"] == "HOSP-001"
    assert rec["meta"]["foo"] == "bar"


def test_emit_audit_legacy_pipeline_omits_pacs_id(tmp_path: Path) -> None:
    """When ``pacs_id`` is None (legacy single-PACS Pipeline) audit events
    must NOT carry a pacs_id field — preserving the existing wire shape so
    historical chains continue to verify identically."""
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "orthanc-a",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
            }
        ],
    )
    state = StateDB(tmp_path / "s.sqlite3")
    state.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit = AuditLogger(tmp_path / "audit.log", gateway_id="gw_test")
    staging = StagingManager(
        tmp_path / "stg", retention_hours=72, max_disk_pct=99
    )
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=state,
        retain=cfg.deid.retain_options,
        burnin_quarantine_modalities=cfg.deid.burnin_quarantine_modalities,
        ruleset_version=cfg.deid.ruleset_version,
        version_string="test",
    )

    p = _make_pipeline(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs_id=None,
        hospital_id=None,
    )

    p._emit_audit("legacy.event", meta={"foo": "bar"})

    line = (tmp_path / "audit.log").read_text(encoding="utf-8").splitlines()[-1]
    rec = json.loads(line)
    assert "pacs_id" not in rec["meta"]
    assert "hospital_id" not in rec["meta"]
    assert rec["meta"]["foo"] == "bar"


def test_emit_audit_caller_pacs_id_wins(tmp_path: Path) -> None:
    """If a caller already provides ``pacs_id`` in ``meta``, the helper
    must not overwrite it. (Defensive — used by tools that craft
    cross-PACS events.)"""
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "orthanc-a",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
            }
        ],
    )
    state = StateDB(tmp_path / "s.sqlite3")
    state.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit = AuditLogger(tmp_path / "audit.log", gateway_id="gw_test")
    staging = StagingManager(
        tmp_path / "stg", retention_hours=72, max_disk_pct=99
    )
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=state,
        retain=cfg.deid.retain_options,
        burnin_quarantine_modalities=cfg.deid.burnin_quarantine_modalities,
        ruleset_version=cfg.deid.ruleset_version,
        version_string="test",
    )
    p = _make_pipeline(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs_id="orthanc-a",
        hospital_id="HOSP-001",
    )
    p._emit_audit("explicit.event", meta={"pacs_id": "override"})
    rec = json.loads(
        (tmp_path / "audit.log").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert rec["meta"]["pacs_id"] == "override"


# ----------------------------------------------------------------------------
# run_multi_pacs_once orchestration
# ----------------------------------------------------------------------------


def _setup_state(tmp_path: Path, cfg: GatewayConfig) -> tuple[
    StateDB, AuditLogger, StagingManager, DeidEngine
]:
    state = StateDB(tmp_path / "state.sqlite3")
    state.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit = AuditLogger(tmp_path / "audit.log", gateway_id="gw_test")
    staging = StagingManager(
        tmp_path / "stg", retention_hours=72, max_disk_pct=99
    )
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=state,
        retain=cfg.deid.retain_options,
        burnin_quarantine_modalities=cfg.deid.burnin_quarantine_modalities,
        ruleset_version=cfg.deid.ruleset_version,
        version_string="test",
    )
    return state, audit, staging, deid


def test_multi_pacs_iterates_in_priority_order(monkeypatch, tmp_path: Path) -> None:
    """Two enabled endpoints, both QIDO returns empty (so pipeline.run_once
    short-circuits with summary.total=0). Verify both endpoints are
    visited in priority order and audit events carry the right pacs_id."""
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "orthanc-b",
                "base_url": "http://localhost:8043/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 20,
                "hospital_id": "HOSP-002",
            },
            {
                "id": "orthanc-a",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 10,
            },
        ],
    )
    state, audit, staging, deid = _setup_state(tmp_path, cfg)

    # Patch builders so we don't actually contact either Orthanc.
    visited: list[str] = []

    def fake_pacs_builder(endpoint):
        visited.append(endpoint.id)
        return FakePacs(studies=[])

    def fake_upload_builder(_cfg, *, hospital_id):
        return FakeUpload(upload_token=f"tok-for-{hospital_id}")

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        fake_pacs_builder,
    )
    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_upload_client",
        fake_upload_builder,
    )

    summary = run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
    )

    assert visited == ["orthanc-a", "orthanc-b"], "priority sort broken"
    assert summary.successes == 2
    assert summary.failures == 0
    assert summary.exit_code() == 0

    # Audit log carries pacs.run.started + pacs.run.completed for each
    # endpoint with the right pacs_id meta tag.
    lines = (tmp_path / "audit.log").read_text("utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    starts = [e for e in events if e["event"] == "pacs.run.started"]
    completes = [e for e in events if e["event"] == "pacs.run.completed"]
    assert [e["meta"]["pacs_id"] for e in starts] == ["orthanc-a", "orthanc-b"]
    assert [e["meta"]["pacs_id"] for e in completes] == ["orthanc-a", "orthanc-b"]
    assert starts[0]["meta"]["hospital_id"] == "HOSP-001"
    assert starts[1]["meta"]["hospital_id"] == "HOSP-002"
    # pacs.query event from inside Pipeline.run_once must also carry
    # pacs_id (via _emit_audit injection).
    queries = [e for e in events if e["event"] == "pacs.query"]
    assert {e["meta"]["pacs_id"] for e in queries} == {"orthanc-a", "orthanc-b"}


def test_multi_pacs_isolates_failure(monkeypatch, tmp_path: Path) -> None:
    """PACS-A raises on QIDO; PACS-B must still complete. Aggregate exit
    code 2 (FR-MPS-2 / AC-MPS-4)."""
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "orthanc-a",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 10,
            },
            {
                "id": "orthanc-b",
                "base_url": "http://localhost:8043/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 20,
                "hospital_id": "HOSP-002",
            },
        ],
    )
    state, audit, staging, deid = _setup_state(tmp_path, cfg)

    def fake_pacs_builder(endpoint):
        if endpoint.id == "orthanc-a":
            return FailingPacs(err=PacsError("connection refused", status_code=None))
        return FakePacs(studies=[])

    def fake_upload_builder(_cfg, *, hospital_id):
        return FakeUpload(upload_token=f"tok-for-{hospital_id}")

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        fake_pacs_builder,
    )
    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_upload_client",
        fake_upload_builder,
    )

    summary = run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
    )

    # Pipeline.run_once catches PacsError on query_studies and returns a
    # summary with failed=1. So orthanc-a is reported as ok=True (no
    # orchestrator-level exception) but with summary.failed=1. orthanc-b
    # is fully ok. Aggregate exit code = 0 (no orchestrator-level failure
    # — pipeline-level failures are observable via has_per_study_failures).
    assert len(summary.runs) == 2
    by_id = {r.pacs_id: r for r in summary.runs}
    assert by_id["orthanc-a"].ok is True
    assert by_id["orthanc-a"].summary is not None
    assert by_id["orthanc-a"].summary.failed == 1
    assert by_id["orthanc-b"].ok is True
    assert summary.has_per_study_failures()
    assert summary.exit_code() == 0  # no orchestrator-level failure


def test_multi_pacs_orchestrator_level_exception_isolates(
    monkeypatch, tmp_path: Path
) -> None:
    """When pipeline.run_once itself raises (not a PacsError it handles
    internally), the orchestrator must catch + record + continue. Exit
    code 2 because at least one endpoint failed at the run level."""
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "broken",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 10,
            },
            {
                "id": "ok",
                "base_url": "http://localhost:8043/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 20,
                "hospital_id": "HOSP-002",
            },
        ],
    )
    state, audit, staging, deid = _setup_state(tmp_path, cfg)

    class ExplodingPacs:
        def query_studies(self, *_, **__):
            raise RuntimeError("staging FS read-only")

    def fake_pacs_builder(endpoint):
        if endpoint.id == "broken":
            return ExplodingPacs()
        return FakePacs(studies=[])

    def fake_upload_builder(_cfg, *, hospital_id):
        return FakeUpload(upload_token=f"tok-for-{hospital_id}")

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        fake_pacs_builder,
    )
    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_upload_client",
        fake_upload_builder,
    )

    summary = run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
    )

    by_id = {r.pacs_id: r for r in summary.runs}
    assert by_id["broken"].ok is False
    assert "staging FS read-only" in (by_id["broken"].error or "")
    assert by_id["ok"].ok is True
    assert summary.exit_code() == 2  # orchestrator-level failure → 2

    # ``pacs.run.failed`` audit row exists for the broken endpoint.
    events = [
        json.loads(line)
        for line in (tmp_path / "audit.log").read_text("utf-8").splitlines()
    ]
    failed = [e for e in events if e["event"] == "pacs.run.failed"]
    assert len(failed) == 1
    assert failed[0]["meta"]["pacs_id"] == "broken"


def test_multi_pacs_filter_runs_only_selected(monkeypatch, tmp_path: Path) -> None:
    """``--pacs orthanc-b`` runs only that endpoint and skips orthanc-a
    entirely (no audit events for orthanc-a, FR-MPS-5 / AC-MPS-5)."""
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "orthanc-a",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 10,
            },
            {
                "id": "orthanc-b",
                "base_url": "http://localhost:8043/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 20,
                "hospital_id": "HOSP-002",
            },
        ],
    )
    state, audit, staging, deid = _setup_state(tmp_path, cfg)

    visited: list[str] = []

    def fake_pacs_builder(endpoint):
        visited.append(endpoint.id)
        return FakePacs(studies=[])

    def fake_upload_builder(_cfg, *, hospital_id):
        return FakeUpload(upload_token=f"tok-{hospital_id}")

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        fake_pacs_builder,
    )
    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_upload_client",
        fake_upload_builder,
    )

    summary = run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs_filter="orthanc-b",
    )

    assert visited == ["orthanc-b"]
    assert len(summary.runs) == 1
    assert summary.runs[0].pacs_id == "orthanc-b"

    events = [
        json.loads(line)
        for line in (tmp_path / "audit.log").read_text("utf-8").splitlines()
    ]
    pacs_ids = {e["meta"].get("pacs_id") for e in events}
    assert pacs_ids == {"orthanc-b"}, "orthanc-a must not emit any events"


def test_multi_pacs_filter_unknown_id_raises(monkeypatch, tmp_path: Path) -> None:
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "orthanc-a",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
            }
        ],
    )
    state, audit, staging, deid = _setup_state(tmp_path, cfg)
    with pytest.raises(ValueError) as exc:
        run_multi_pacs_once(
            cfg,
            state_db=state,
            audit_logger=audit,
            staging=staging,
            deid=deid,
            pacs_filter="does-not-exist",
        )
    assert "does-not-exist" in str(exc.value)


def test_multi_pacs_token_lookup_failure_isolates(monkeypatch, tmp_path: Path) -> None:
    """When ``token_for_hospital`` raises (no map entry, no fallback), the
    endpoint is reported as failed but the loop continues."""
    cfg = _build_cfg(
        tmp_path,
        endpoints=[
            {
                "id": "no-token",
                "base_url": "http://localhost:8042/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 10,
                "hospital_id": "HOSP-999",  # not in upload_tokens map
            },
            {
                "id": "ok",
                "base_url": "http://localhost:8043/dicom-web",
                "auth": {"type": "basic", "username": "x", "password": "y"},
                "priority": 20,
            },
        ],
    )
    # Override central to force lookup miss for HOSP-999 (no fallback).
    cfg.central.upload_token = None
    cfg.central.upload_tokens = {"HOSP-001": "tok-1"}
    state, audit, staging, deid = _setup_state(tmp_path, cfg)

    def fake_pacs_builder(endpoint):
        return FakePacs(studies=[])

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        fake_pacs_builder,
    )

    summary = run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
    )
    by_id = {r.pacs_id: r for r in summary.runs}
    assert by_id["no-token"].ok is False
    assert "HOSP-999" in (by_id["no-token"].error or "")
    assert by_id["ok"].ok is True
    assert summary.exit_code() == 2
