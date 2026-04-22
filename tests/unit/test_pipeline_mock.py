"""Pipeline end-to-end against the FastAPI mock central and a stubbed PACS.

We avoid running a real PACS container in unit tests by stubbing the
PACS client at the object level. The de-id engine, staging, and upload paths
run for real.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from radivault_gateway.audit import AuditLogger, verify_chain
from radivault_gateway.config import GatewayConfig
from radivault_gateway.deid import DeidEngine
from radivault_gateway.orchestrator import Pipeline
from radivault_gateway.pacs import FetchResult, StudySummary
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB, StudyState
from radivault_gateway.upload import UploadClient


@dataclass
class FakePacs:
    studies: list[StudySummary]
    fetch_dir_src: Path

    def query_studies(self, *args, **kwargs):
        return self.studies

    def fetch_study(self, study_uid, out_dir):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for src in sorted(self.fetch_dir_src.glob("*.dcm")):
            shutil.copy(src, out / src.name)
        paths = sorted(out.glob("*.dcm"))
        return FetchResult(
            study_instance_uid=study_uid,
            instance_paths=paths,
            bytes_total=sum(p.stat().st_size for p in paths),
            duration_ms=5,
        )


def _build_config(tmp_path: Path) -> GatewayConfig:
    import yaml

    salt = tmp_path / "salt"
    salt.write_text("0123456789abcdef" * 2)
    data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
            "hospital_id": "hosp_test",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": {
            "base_url": "http://pacs.invalid",
            "auth": {"type": "bearer", "token": "tok"},
            "max_concurrency": 2,
            "poll_interval_seconds": 60,
            "query": {"modalities": ["MR"], "lookback_days": 7},
        },
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt": f"${{file:{salt}}}",
            "salt_version": 1,
        },
        "staging": {
            "root": str(tmp_path / "stg"),
            "retention_hours": 72,
            "max_disk_pct": 99,
        },
        "state": {"db_path": str(tmp_path / "state.sqlite3")},
        "audit": {"path": str(tmp_path / "audit.log"), "anchor_interval_seconds": 3600},
        "central": {"base_url": "http://testserver", "upload_token": "tok-abc"},
        "logging": {"level": "INFO", "json": True},
    }
    cfg_path = tmp_path / "gateway.yml"
    cfg_path.write_text(yaml.safe_dump(data))
    from radivault_gateway.config import load_config

    return load_config(cfg_path)


def test_pipeline_happy_path_end_to_end(make_synthetic_study, tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_CENTRAL_DUMP", str(tmp_path / "dump"))
    monkeypatch.setenv("MOCK_CENTRAL_TOKEN", "tok-abc")

    import radivault_mock_central.main as mod

    importlib.reload(mod)
    test_client = TestClient(mod.app)

    # Build real synthetic DICOMs.
    study_src = make_synthetic_study(n_instances=3)
    studies = [
        StudySummary(
            study_instance_uid="1.2.3.FAKE",
            patient_id="P-001",
            study_date="20260401",
            modalities_in_study=["MR"],
            num_instances=3,
        )
    ]

    cfg = _build_config(tmp_path)
    db = StateDB(cfg.state.db_path)
    db.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit = AuditLogger(cfg.audit.path, gateway_id=cfg.agent.gateway_id)
    staging = StagingManager(cfg.staging.root, max_disk_pct=cfg.staging.max_disk_pct)
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=db,
        retain=cfg.deid.retain_options,
    )
    pacs = FakePacs(studies=studies, fetch_dir_src=study_src)

    # Upload client uses MockTransport bridging to FastAPI TestClient.
    upload = UploadClient("http://testserver", upload_token="tok-abc", max_retries=1)

    def _bridge(request: httpx.Request) -> httpx.Response:
        resp = test_client.request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
            params=dict(request.url.params),
        )
        return httpx.Response(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
        )

    upload._client = httpx.Client(
        transport=httpx.MockTransport(_bridge),
        base_url="http://testserver",
        headers={"Authorization": "Bearer tok-abc"},
        timeout=30.0,
    )

    pipeline = Pipeline(
        cfg,
        state_db=db,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs=pacs,
        upload=upload,
    )

    summary = pipeline.run_once(since=date(2026, 4, 1), until=date(2026, 4, 30))
    assert summary.uploaded == 1
    assert summary.failed == 0
    assert summary.outcomes[0].state == StudyState.UPLOADED
    # Staging was cleaned up (FR-15, AC-11)
    pseudo_uid = summary.outcomes[0].pseudo_study_uid
    assert pseudo_uid is not None
    assert not (tmp_path / "stg" / pseudo_uid).exists()
    # Audit chain verifies
    vr = verify_chain(cfg.audit.path)
    assert vr.ok is True
    # Dump dir under mock central got the manifest + dcm files.
    dump = Path(os.environ["MOCK_CENTRAL_DUMP"]) / pseudo_uid
    assert dump.exists()
    assert (dump / "manifest.json").exists()
    manifest = json.loads((dump / "manifest.json").read_text())
    assert manifest["pseudo_study_uid"] == pseudo_uid
    # AC-6: original study UID must not appear in manifest bytes.
    assert b"1.2.3.FAKE" not in (dump / "manifest.json").read_bytes()


def test_pipeline_quarantines_burned_in_studies(make_synthetic_study, tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_CENTRAL_DUMP", str(tmp_path / "dump"))
    monkeypatch.setenv("MOCK_CENTRAL_TOKEN", "tok-abc")

    import radivault_mock_central.main as mod

    importlib.reload(mod)
    test_client = TestClient(mod.app)

    study_src = make_synthetic_study(n_instances=1, burned_in="YES")
    studies = [
        StudySummary(
            study_instance_uid="1.2.3.BURN",
            patient_id="P-002",
            study_date="20260402",
            modalities_in_study=["MR"],
            num_instances=1,
        )
    ]

    cfg = _build_config(tmp_path)
    db = StateDB(cfg.state.db_path)
    audit = AuditLogger(cfg.audit.path, gateway_id=cfg.agent.gateway_id)
    staging = StagingManager(cfg.staging.root)
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=db,
    )
    pacs = FakePacs(studies=studies, fetch_dir_src=study_src)
    upload = UploadClient("http://testserver", upload_token="tok-abc", max_retries=1)

    def _bridge(request: httpx.Request) -> httpx.Response:
        resp = test_client.request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
            params=dict(request.url.params),
        )
        return httpx.Response(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
        )

    upload._client = httpx.Client(
        transport=httpx.MockTransport(_bridge),
        base_url="http://testserver",
        headers={"Authorization": "Bearer tok-abc"},
    )
    pipeline = Pipeline(
        cfg,
        state_db=db,
        audit_logger=audit,
        staging=staging,
        deid=deid,
        pacs=pacs,
        upload=upload,
    )
    summary = pipeline.run_once()
    assert summary.quarantined == 1
    assert summary.uploaded == 0
    # Central dump should not contain this study.
    assert not any(
        p.name.startswith("1.2") for p in Path(os.environ["MOCK_CENTRAL_DUMP"]).glob("*")
    )
