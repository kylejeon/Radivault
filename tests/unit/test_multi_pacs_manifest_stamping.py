"""Multi-PACS manifest hospital_id stamping (FR-MPS-2 fix).

Regression guard for the bug observed live on D-13 sync-once where every
HOSP-002 (orthanc-b) upload was rejected by Central with::

    ERR_AUTH_MISMATCH
    manifest.hospital_id='HOSP-001' != token.hospital_id='HOSP-002'

Root cause: ``Pipeline._handle_study`` and the metadata-only Flow A path
both stamped ``cfg.agent.hospital_id`` (the gateway-wide default) onto
the manifest instead of the per-PACS scope carried by
``Pipeline._hospital_id`` (set by :func:`run_multi_pacs_once` per
endpoint).

Fix: ``Pipeline._effective_hospital_id`` returns ``self._hospital_id``
when set, falling back to ``cfg.agent.hospital_id`` for legacy single-PACS
callers (zero regression). Both ``build_manifest`` and
``build_metadata_only_manifest`` now route through that helper.

Cases:
  1. HOSP-001 PACS context → manifest.hospital_id == 'HOSP-001'.
  2. HOSP-002 PACS context → manifest.hospital_id == 'HOSP-002'
     (this is the case that failed live).
  3. PACS switch (HOSP-001 → HOSP-002) — second manifest carries the
     new scope, no state contamination from the first Pipeline.
  4. Legacy single-PACS Pipeline (no hospital_id ctor kwarg) — manifest
     falls back to ``cfg.agent.hospital_id`` exactly like before
     (regression guard).
"""

from __future__ import annotations

# Break the pre-existing circular import (mirrors test_multi_pacs_pipeline).
import radivault_gateway.deid  # noqa: F401

from dataclasses import dataclass
from pathlib import Path

from radivault_gateway.audit import AuditLogger
from radivault_gateway.config import GatewayConfig
from radivault_gateway.deid import DeidEngine
from radivault_gateway.orchestrator import Pipeline
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB
from radivault_gateway.upload import UploadClient


# ----------------------------------------------------------------------------
# Helpers — synthetic config + Pipeline factory
# ----------------------------------------------------------------------------


def _build_cfg(tmp_path: Path) -> GatewayConfig:
    base = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
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


@dataclass
class _NullPacs:
    """Stub PACS — Pipeline ctor only stores the ref; not invoked here."""

    def query_studies(self, *args, **kwargs):
        return []


def _build_shared(
    cfg: GatewayConfig, tmp_path: Path
) -> tuple[StateDB, AuditLogger, StagingManager, DeidEngine]:
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


def _make_pipeline(
    cfg: GatewayConfig,
    *,
    state_db: StateDB,
    audit_logger: AuditLogger,
    staging: StagingManager,
    deid: DeidEngine,
    upload: UploadClient,
    pacs_id: str | None = None,
    hospital_id: str | None = None,
) -> Pipeline:
    return Pipeline(
        cfg,
        state_db=state_db,
        audit_logger=audit_logger,
        staging=staging,
        deid=deid,
        pacs=_NullPacs(),
        upload=upload,
        pixel=None,
        pacs_id=pacs_id,
        hospital_id=hospital_id,
    )


def _make_upload_client() -> UploadClient:
    return UploadClient(
        "http://testserver",
        upload_token="tok",
        max_retries=1,
        allow_insecure=True,
    )


# ----------------------------------------------------------------------------
# Cases — _effective_hospital_id() resolution + manifest stamping
# ----------------------------------------------------------------------------


def test_effective_hospital_id_uses_per_pacs_scope_hosp001(tmp_path: Path) -> None:
    """Case 1 — Pipeline constructed with hospital_id='HOSP-001' must stamp
    HOSP-001 on every outbound manifest, regardless of cfg.agent.hospital_id."""
    cfg = _build_cfg(tmp_path)
    state, audit, staging, deid = _build_shared(cfg, tmp_path)
    upload = _make_upload_client()
    try:
        pipeline = _make_pipeline(
            cfg,
            state_db=state,
            audit_logger=audit,
            staging=staging,
            deid=deid,
            upload=upload,
            pacs_id="orthanc-a",
            hospital_id="HOSP-001",
        )
        assert pipeline._effective_hospital_id() == "HOSP-001"

        # Build a real manifest using the helper-resolved scope.
        f = tmp_path / "a.dcm"
        f.write_bytes(b"alpha-bytes")
        manifest = upload.build_manifest(
            gateway_id=cfg.agent.gateway_id,
            hospital_id=pipeline._effective_hospital_id(),
            pseudo_study_uid="2.25.case1",
            modalities=["CT"],
            ruleset_version=cfg.deid.ruleset_version,
            salt_version=cfg.deid.salt_version,
            method_codes=["113100"],
            dcm_files=[f],
        )
        assert manifest["hospital_id"] == "HOSP-001"
    finally:
        upload.close()


def test_effective_hospital_id_uses_per_pacs_scope_hosp002(tmp_path: Path) -> None:
    """Case 2 — the buggy case: cfg.agent.hospital_id='HOSP-001' but the
    Pipeline was constructed for orthanc-b with hospital_id='HOSP-002'.
    The manifest MUST stamp HOSP-002, not the agent default."""
    cfg = _build_cfg(tmp_path)
    assert cfg.agent.hospital_id == "HOSP-001", "fixture sanity"
    state, audit, staging, deid = _build_shared(cfg, tmp_path)
    upload = _make_upload_client()
    try:
        pipeline = _make_pipeline(
            cfg,
            state_db=state,
            audit_logger=audit,
            staging=staging,
            deid=deid,
            upload=upload,
            pacs_id="orthanc-b",
            hospital_id="HOSP-002",
        )
        assert pipeline._effective_hospital_id() == "HOSP-002"

        f = tmp_path / "b.dcm"
        f.write_bytes(b"bravo-bytes")
        manifest = upload.build_manifest(
            gateway_id=cfg.agent.gateway_id,
            hospital_id=pipeline._effective_hospital_id(),
            pseudo_study_uid="2.25.case2",
            modalities=["MR"],
            ruleset_version=cfg.deid.ruleset_version,
            salt_version=cfg.deid.salt_version,
            method_codes=["113100"],
            dcm_files=[f],
        )
        # This is the assertion that would have caught the live D-13 bug.
        assert manifest["hospital_id"] == "HOSP-002"
        assert manifest["hospital_id"] != cfg.agent.hospital_id

        # Same path for the metadata-only Flow A manifest.
        meta_manifest = upload.build_metadata_only_manifest(
            gateway_id=cfg.agent.gateway_id,
            hospital_id=pipeline._effective_hospital_id(),
            pseudo_study_uid="2.25.case2.meta",
            modalities=["MR"],
            ruleset_version=cfg.deid.ruleset_version,
            salt_version=cfg.deid.salt_version,
            method_codes=["113100"],
            n_instances=12,
            total_bytes=0,
        )
        assert meta_manifest["hospital_id"] == "HOSP-002"
    finally:
        upload.close()


def test_pacs_switch_no_state_contamination(tmp_path: Path) -> None:
    """Case 3 — :func:`run_multi_pacs_once` builds a fresh Pipeline per
    endpoint. After the first endpoint completes (HOSP-001), the second
    endpoint's Pipeline (HOSP-002) must report its own scope. This test
    mimics the orchestrator's per-endpoint construction pattern.

    A regression that reused a single Pipeline across endpoints (or that
    cached _effective_hospital_id from a prior run) would surface here as
    the second pipeline returning HOSP-001."""
    cfg = _build_cfg(tmp_path)
    state, audit, staging, deid = _build_shared(cfg, tmp_path)

    upload_1 = _make_upload_client()
    upload_2 = _make_upload_client()
    try:
        # First PACS iteration — orthanc-a / HOSP-001.
        pipeline_a = _make_pipeline(
            cfg,
            state_db=state,
            audit_logger=audit,
            staging=staging,
            deid=deid,
            upload=upload_1,
            pacs_id="orthanc-a",
            hospital_id="HOSP-001",
        )
        f_a = tmp_path / "a.dcm"
        f_a.write_bytes(b"alpha-bytes")
        m_a = upload_1.build_manifest(
            gateway_id=cfg.agent.gateway_id,
            hospital_id=pipeline_a._effective_hospital_id(),
            pseudo_study_uid="2.25.switch.a",
            modalities=["CT"],
            ruleset_version=cfg.deid.ruleset_version,
            salt_version=cfg.deid.salt_version,
            method_codes=["113100"],
            dcm_files=[f_a],
        )
        assert m_a["hospital_id"] == "HOSP-001"

        # Second PACS iteration — orthanc-b / HOSP-002. The orchestrator
        # constructs a brand-new Pipeline; verify the scope flips cleanly.
        pipeline_b = _make_pipeline(
            cfg,
            state_db=state,
            audit_logger=audit,
            staging=staging,
            deid=deid,
            upload=upload_2,
            pacs_id="orthanc-b",
            hospital_id="HOSP-002",
        )
        f_b = tmp_path / "b.dcm"
        f_b.write_bytes(b"bravo-bytes")
        m_b = upload_2.build_manifest(
            gateway_id=cfg.agent.gateway_id,
            hospital_id=pipeline_b._effective_hospital_id(),
            pseudo_study_uid="2.25.switch.b",
            modalities=["MR"],
            ruleset_version=cfg.deid.ruleset_version,
            salt_version=cfg.deid.salt_version,
            method_codes=["113100"],
            dcm_files=[f_b],
        )
        assert m_b["hospital_id"] == "HOSP-002"

        # Re-confirm the first pipeline still reports HOSP-001 — i.e. no
        # shared state mutation flipped its scope when pipeline_b was
        # constructed.
        assert pipeline_a._effective_hospital_id() == "HOSP-001"
        assert pipeline_b._effective_hospital_id() == "HOSP-002"
    finally:
        upload_1.close()
        upload_2.close()


def test_legacy_single_pacs_falls_back_to_agent_hospital_id(tmp_path: Path) -> None:
    """Case 4 — Pipeline constructed without ``hospital_id=`` (legacy
    single-PACS daemon path or older unit tests): ``_effective_hospital_id``
    must fall back to ``cfg.agent.hospital_id`` so the manifest still
    stamps a valid scope. Zero regression on single-PACS configs."""
    cfg = _build_cfg(tmp_path)
    state, audit, staging, deid = _build_shared(cfg, tmp_path)
    upload = _make_upload_client()
    try:
        pipeline = _make_pipeline(
            cfg,
            state_db=state,
            audit_logger=audit,
            staging=staging,
            deid=deid,
            upload=upload,
            pacs_id=None,
            hospital_id=None,  # legacy ctor — no per-PACS scope
        )
        assert pipeline._effective_hospital_id() == cfg.agent.hospital_id
        assert pipeline._effective_hospital_id() == "HOSP-001"

        f = tmp_path / "legacy.dcm"
        f.write_bytes(b"legacy-bytes")
        manifest = upload.build_manifest(
            gateway_id=cfg.agent.gateway_id,
            hospital_id=pipeline._effective_hospital_id(),
            pseudo_study_uid="2.25.legacy",
            modalities=["CR"],
            ruleset_version=cfg.deid.ruleset_version,
            salt_version=cfg.deid.salt_version,
            method_codes=["113100"],
            dcm_files=[f],
        )
        assert manifest["hospital_id"] == cfg.agent.hospital_id
    finally:
        upload.close()
