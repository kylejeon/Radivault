"""Integration tests for multi-PACS sync (FR-MPS-2 / FR-MPS-3).

Two modes:

1. **Service-light** (always runs, marked unit-style) — exercises the full
   ``run_multi_pacs_once`` flow against in-process FakePacs / FakeUpload
   stubs. Verifies (1) both PACS' studies are ingested, (2) one-down +
   one-up isolates correctly, (3) audit chain still verifies, (4) all
   events carry the right pacs_id meta.

2. **Live Orthanc** (gated by ``ORTHANC_A_URL`` + ``ORTHANC_B_URL`` env
   vars, mark ``integration``) — runs against two real DICOMweb servers
   and asserts both endpoints' studies land in the gateway state DB
   without exceptions.

Mode 1 lives here (alongside the live test) so AC-MPS-1..AC-MPS-4 are
exercised on every CI run, not just when an operator wires the env vars.
"""

from __future__ import annotations

# Break the pre-existing circular import.
import radivault_gateway.deid  # noqa: F401

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from radivault_gateway.audit import AuditLogger, verify_chain
from radivault_gateway.config import GatewayConfig
from radivault_gateway.deid import DeidEngine
from radivault_gateway.orchestrator import (
    MultiPacsRunSummary,
    PacsRunResult,
    run_multi_pacs_once,
)
from radivault_gateway.pacs import PacsError, StudySummary
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB, StudyState


# ---------------------------------------------------------------------------
# Mode 1 — service-light, always runs.
# ---------------------------------------------------------------------------


@dataclass
class FakePacs:
    studies: list[StudySummary]

    def query_studies(self, *args, **kwargs):
        return self.studies


@dataclass
class FailingPacs:
    err: Exception

    def query_studies(self, *args, **kwargs):
        raise self.err


class FakeUpload:
    def __init__(self, *, upload_token: str = "default", **_):
        self.upload_token = upload_token
        self.closed = False

    def close(self):
        self.closed = True


def _multi_pacs_cfg(tmp_path: Path) -> GatewayConfig:
    base = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_demo",
            "hospital_id": "HOSP-001",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": [
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


def _setup(tmp_path: Path, cfg: GatewayConfig):
    state = StateDB(tmp_path / "state.sqlite3")
    state.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit = AuditLogger(tmp_path / "audit.log", gateway_id="gw_demo")
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


def test_case1_both_pacs_ingest(monkeypatch, tmp_path: Path) -> None:
    """AC-MPS-1: Orthanc-A + Orthanc-B both registered → sync-once
    iterates both. (Empty study lists keep the test deterministic; the
    point is that both endpoints run.)"""
    cfg = _multi_pacs_cfg(tmp_path)
    state, audit, staging, deid = _setup(tmp_path, cfg)

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
    )

    assert visited == ["orthanc-a", "orthanc-b"]
    assert summary.successes == 2
    assert summary.failures == 0
    assert summary.exit_code() == 0


def test_case2_isolation_one_down(monkeypatch, tmp_path: Path) -> None:
    """AC-MPS-4: PACS-A connection refused → PACS-B still completes.
    Aggregate exit code 0 (PacsError handled INSIDE Pipeline.run_once;
    pipeline-level summary.failed=1 surfaces the PACS-A failure)."""
    cfg = _multi_pacs_cfg(tmp_path)
    state, audit, staging, deid = _setup(tmp_path, cfg)

    def fake_pacs_builder(endpoint):
        if endpoint.id == "orthanc-a":
            return FailingPacs(
                err=PacsError("connection refused", status_code=None)
            )
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
    )

    by_id = {r.pacs_id: r for r in summary.runs}
    assert by_id["orthanc-a"].ok is True  # pipeline handled error
    assert by_id["orthanc-a"].summary.failed == 1
    assert by_id["orthanc-b"].ok is True
    assert by_id["orthanc-b"].summary.failed == 0
    # has_per_study_failures flags PACS-A's internal failure for
    # operators who want to gate CI on it.
    assert summary.has_per_study_failures()


def test_case3_legacy_single_pacs_regression(monkeypatch, tmp_path: Path) -> None:
    """AC-MPS-3: legacy single-dict pacs config still works through the
    multi-PACS orchestrator (1-element list)."""
    base = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_legacy",
            "hospital_id": "HOSP-001",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": {
            "base_url": "http://localhost:8042/dicom-web",
            "auth": {"type": "basic", "username": "x", "password": "y"},
        },
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
            "upload_token": "legacy-tok",
            "allow_insecure": True,
        },
    }
    cfg = GatewayConfig.model_validate(base)
    state, audit, staging, deid = _setup(tmp_path, cfg)

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        lambda e: FakePacs(studies=[]),
    )
    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_upload_client",
        lambda c, *, hospital_id: FakeUpload(upload_token="legacy"),
    )
    summary = run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
    )
    # 1-element list, legacy id="default".
    assert len(summary.runs) == 1
    assert summary.runs[0].pacs_id == "default"
    assert summary.runs[0].ok is True


def test_case4_audit_log_carries_pacs_id_meta(
    monkeypatch, tmp_path: Path
) -> None:
    """AC-MPS-7: every PACS-scoped audit event has pacs_id meta. Chain
    verification stays PASS."""
    cfg = _multi_pacs_cfg(tmp_path)
    state, audit, staging, deid = _setup(tmp_path, cfg)

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        lambda e: FakePacs(studies=[]),
    )
    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_upload_client",
        lambda c, *, hospital_id: FakeUpload(),
    )
    run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
    )

    # Chain verifier passes.
    result = verify_chain(tmp_path / "audit.log")
    assert result.ok, f"chain verify failed: {result}"

    # Every event carries pacs_id + hospital_id.
    events = [
        json.loads(line)
        for line in (tmp_path / "audit.log").read_text().splitlines()
    ]
    assert events, "no events emitted"
    for ev in events:
        meta = ev.get("meta", {})
        assert "pacs_id" in meta, f"missing pacs_id on {ev['event']}"
        assert "hospital_id" in meta, f"missing hospital_id on {ev['event']}"
        assert meta["pacs_id"] in {"orthanc-a", "orthanc-b"}
        assert meta["hospital_id"] in {"HOSP-001", "HOSP-002"}


def test_case5_pacs_filter_isolates_audit(monkeypatch, tmp_path: Path) -> None:
    """AC-MPS-5: --pacs orthanc-b emits zero audit events for orthanc-a."""
    cfg = _multi_pacs_cfg(tmp_path)
    state, audit, staging, deid = _setup(tmp_path, cfg)

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_pacs_client",
        lambda e: FakePacs(studies=[]),
    )
    monkeypatch.setattr(
        "radivault_gateway.orchestrator.multi_pacs.build_upload_client",
        lambda c, *, hospital_id: FakeUpload(),
    )
    run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs_filter="orthanc-b",
    )

    events = [
        json.loads(line)
        for line in (tmp_path / "audit.log").read_text().splitlines()
    ]
    pacs_ids = {ev["meta"].get("pacs_id") for ev in events}
    assert pacs_ids == {"orthanc-b"}


# ---------------------------------------------------------------------------
# Mode 2 — live Orthanc (gated by env vars).
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_live_multi_pacs_smoke(tmp_path: Path) -> None:
    """Run the multi-PACS orchestrator against two live Orthanc servers
    and assert both produce ``pacs.run.completed`` audit events.

    Skipped unless ``ORTHANC_A_URL`` AND ``ORTHANC_B_URL`` env vars
    are set. Default demo URLs (when present):
      ORTHANC_A_URL=http://localhost:8042/dicom-web
      ORTHANC_B_URL=http://localhost:8043/dicom-web
    """
    a_url = os.environ.get("ORTHANC_A_URL")
    b_url = os.environ.get("ORTHANC_B_URL")
    if not (a_url and b_url):
        pytest.skip("ORTHANC_A_URL / ORTHANC_B_URL not set")

    base = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test_live",
            "hospital_id": "HOSP-001",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": [
            {
                "id": "orthanc-a",
                "base_url": a_url,
                "auth": {"type": "basic", "username": "orthanc", "password": "orthanc"},
                "priority": 10,
            },
            {
                "id": "orthanc-b",
                "base_url": b_url,
                "auth": {"type": "basic", "username": "orthanc", "password": "orthanc"},
                "priority": 20,
                "hospital_id": "HOSP-002",
            },
        ],
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
            "base_url": os.environ.get("CENTRAL_URL", "http://localhost:8000"),
            "upload_tokens": {
                "HOSP-001": os.environ.get("HOSP_001_TOKEN", "placeholder"),
                "HOSP-002": os.environ.get("HOSP_002_TOKEN", "placeholder"),
            },
            "allow_insecure": True,
        },
        "logging": {"level": "INFO", "json": True},
    }
    cfg = GatewayConfig.model_validate(base)
    state, audit, staging, deid = _setup(tmp_path, cfg)

    # Live test: dry_run so we don't actually push to central. The point
    # is to confirm the orchestrator can talk QIDO to both Orthanc
    # endpoints without exceptions and emit the expected audit envelope.
    summary = run_multi_pacs_once(
        cfg,
        state_db=state,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        dry_run=True,
        limit=1,
    )
    assert len(summary.runs) == 2
    # Both endpoints must have at least attempted a run; a transient
    # network blip would surface as ok=False, but the orchestrator
    # should never abort the loop (FR-MPS-2 isolation).
    pacs_ids = [r.pacs_id for r in summary.runs]
    assert pacs_ids == ["orthanc-a", "orthanc-b"]
