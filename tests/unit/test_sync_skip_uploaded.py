"""gateway-sync-skip-uploaded — ensure already-uploaded studies short-circuit.

Dev-spec §4 PACS + §8 State DB schema. The Gateway's ``_process_study`` must
consult the state DB before touching PACS / de-id when an original Study
Instance UID has an ``uploaded`` row keyed by its SHA-256 prefix hash. Central
already handles replayed manifests via idempotency, so correctness is not at
risk — this is a bandwidth / wall-clock optimisation that the Kyle demo
re-seeds depend on.

Coverage:
1. ``is_study_uploaded`` positive + negative + wrong-state.
2. ``mark_state(..., original_uid=...)`` persists the hash.
3. Pipeline short-circuits — PACS ``fetch_study`` count remains 0.
4. RunSummary counts a skip in ``skipped`` (not ``uploaded``).
5. Legacy rows with NULL ``original_study_uid_hash`` are NOT skipped
   (regression guard for the migration transition window).
6. Migration is idempotent — opening the DB twice does not error or double
   the column.
"""

from __future__ import annotations

import hashlib
import importlib
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from radivault_gateway.state import StateDB, StudyState

# ---------------------------------------------------------------------------
# State DB unit tests
# ---------------------------------------------------------------------------


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def test_is_study_uploaded_returns_true_when_original_hash_matches(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    original = "1.2.840.113619.2.5.111.example"
    db.upsert_study_job("2.25.pseudo-a", state=StudyState.DEIDED)
    db.mark_state("2.25.pseudo-a", StudyState.UPLOADED, original_uid=original)

    assert db.is_study_uploaded(original) is True
    # Column is populated with the 16-char prefix exactly.
    row = db._conn.execute(
        "SELECT original_study_uid_hash FROM study_job WHERE pseudo_study_uid=?",
        ("2.25.pseudo-a",),
    ).fetchone()
    assert row["original_study_uid_hash"] == _sha16(original)
    db.close()


def test_is_study_uploaded_returns_false_for_unknown_uid(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_study_job("2.25.pseudo-a", state=StudyState.UPLOADED)
    db.mark_state(
        "2.25.pseudo-a", StudyState.UPLOADED, original_uid="1.2.840.a.known"
    )

    assert db.is_study_uploaded("1.2.840.a.unknown") is False
    db.close()


def test_is_study_uploaded_returns_false_for_non_uploaded_state(tmp_path: Path) -> None:
    """A study that went through DEIDED/FAILED_UPLOAD should NOT be skipped;
    the pipeline still needs to resume it."""
    db = StateDB(tmp_path / "state.sqlite3")
    original = "1.2.840.still.pending"
    db.upsert_study_job("2.25.pseudo-b", state=StudyState.DEIDED)
    db.mark_state("2.25.pseudo-b", StudyState.FAILED_UPLOAD, original_uid=original)

    assert db.is_study_uploaded(original) is False
    db.close()


def test_is_study_uploaded_false_for_legacy_null_hash_rows(tmp_path: Path) -> None:
    """Rows inserted before the migration have NULL
    ``original_study_uid_hash``. They must not short-circuit because we
    cannot recover the original UID from the one-way pseudo derivation —
    they simply pay a one-off re-fetch on the first post-migration run."""
    db = StateDB(tmp_path / "state.sqlite3")
    # Simulate a pre-migration UPLOADED row by upserting + marking UPLOADED
    # without ``original_uid``.
    db.upsert_study_job("2.25.pseudo-legacy", state=StudyState.DEIDED)
    db.mark_state("2.25.pseudo-legacy", StudyState.UPLOADED)  # original_uid omitted

    # Invariant: the hash column is NULL, and the lookup for the corresponding
    # original UID must return False (forcing re-processing on next sync).
    row = db._conn.execute(
        "SELECT original_study_uid_hash FROM study_job WHERE pseudo_study_uid=?",
        ("2.25.pseudo-legacy",),
    ).fetchone()
    assert row["original_study_uid_hash"] is None
    assert db.is_study_uploaded("1.2.840.legacy.original") is False
    db.close()


def test_migration_is_idempotent_on_reopen(tmp_path: Path) -> None:
    """Opening the same DB twice must not raise and must keep a single
    ``original_study_uid_hash`` column."""
    path = tmp_path / "state.sqlite3"
    db1 = StateDB(path)
    db1.close()
    db2 = StateDB(path)  # second open triggers _migrate again
    cols = [row["name"] for row in db2._conn.execute("PRAGMA table_info('study_job')").fetchall()]
    assert cols.count("original_study_uid_hash") == 1
    db2.close()


def test_migration_upgrades_pre_existing_db_without_hash_column(tmp_path: Path) -> None:
    """A DB created by an older Gateway (no ``original_study_uid_hash``) must
    be ALTERed in place. We simulate by building a minimal legacy schema then
    opening it through :class:`StateDB`."""
    path = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE study_job (
            pseudo_study_uid  TEXT PRIMARY KEY,
            state             TEXT NOT NULL,
            modalities        TEXT,
            n_instances       INTEGER,
            n_bytes           INTEGER,
            first_seen_at     TEXT NOT NULL,
            deided_at         TEXT,
            uploaded_at       TEXT,
            last_error        TEXT,
            retry_count       INTEGER NOT NULL DEFAULT 0,
            central_job_id    TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO study_job (pseudo_study_uid, state, first_seen_at) VALUES (?, ?, ?)",
        ("2.25.legacy", "uploaded", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    db = StateDB(path)
    cols = {row["name"] for row in db._conn.execute("PRAGMA table_info('study_job')").fetchall()}
    assert "original_study_uid_hash" in cols
    # Legacy row's hash is NULL — skip must return False.
    assert db.is_study_uploaded("1.2.840.legacy.anything") is False
    db.close()


# ---------------------------------------------------------------------------
# Pipeline integration — skip short-circuits fetch + de-id + upload
# ---------------------------------------------------------------------------


def _build_config(tmp_path: Path):
    """Construct a GatewayConfig. Imports are local to avoid the circular
    import that `radivault_gateway.config` triggers when this test module is
    collected in isolation (see test_pipeline_mock.py for the same workaround)."""
    import yaml

    from radivault_gateway.config import load_config

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
        "central": {
            "base_url": "http://testserver",
            "upload_token": "tok-abc",
            "allow_insecure": True,
        },
        "logging": {"level": "INFO", "json": True},
    }
    cfg_path = tmp_path / "gateway.yml"
    cfg_path.write_text(yaml.safe_dump(data))
    return load_config(cfg_path)


def _make_counting_pacs(studies, fetch_dir_src: Path):
    """Build a fake PACS that counts fetch invocations. Defined here so the
    ``FetchResult`` / ``StudySummary`` imports stay lazy."""
    from radivault_gateway.pacs import FetchResult

    @dataclass
    class CountingPacs:
        studies: list
        fetch_dir_src: Path
        fetch_calls: int = 0
        query_calls: int = 0

        def query_studies(self, *args, **kwargs):
            self.query_calls += 1
            return self.studies

        def fetch_study(self, study_uid, out_dir):
            self.fetch_calls += 1
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

    return CountingPacs(studies=studies, fetch_dir_src=fetch_dir_src)


def test_pipeline_skips_already_uploaded_without_fetch_or_deid(
    make_synthetic_study, tmp_path, monkeypatch
):
    """When an original Study Instance UID has an UPLOADED row with a matching
    hash, ``_process_study`` must short-circuit at the state-DB check. The
    PACS client's ``fetch_study`` must never run, the upload bridge must
    never be hit (enforced via ``_refuse`` below), and the RunSummary must
    record the cycle as ``skipped`` — not ``uploaded``."""
    import httpx

    from radivault_gateway.audit import AuditLogger
    from radivault_gateway.deid import DeidEngine
    from radivault_gateway.orchestrator import Pipeline
    from radivault_gateway.pacs import StudySummary
    from radivault_gateway.staging import StagingManager
    from radivault_gateway.upload import UploadClient

    monkeypatch.setenv("MOCK_CENTRAL_DUMP", str(tmp_path / "dump"))
    monkeypatch.setenv("MOCK_CENTRAL_TOKEN", "tok-abc")

    study_src = make_synthetic_study(n_instances=2)
    original_uid = "1.2.3.SKIP.ME"
    studies = [
        StudySummary(
            study_instance_uid=original_uid,
            patient_id="P-001",
            study_date="20260401",
            modalities_in_study=["MR"],
            num_instances=2,
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
    # Pre-seed state as if a prior sync had completed the upload.
    db.upsert_study_job("2.25.pseudo-skipme", state=StudyState.DEIDED)
    db.mark_state("2.25.pseudo-skipme", StudyState.UPLOADED, original_uid=original_uid)

    pacs = _make_counting_pacs(studies, study_src)
    audit = AuditLogger(cfg.audit.path, gateway_id=cfg.agent.gateway_id)
    staging = StagingManager(cfg.staging.root, max_disk_pct=cfg.staging.max_disk_pct)
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=db,
        retain=cfg.deid.retain_options,
    )
    upload = UploadClient(
        "http://testserver", upload_token="tok-abc", max_retries=1, allow_insecure=True
    )

    def _refuse(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"upload client must not be called on skip — got {request.method} {request.url}"
        )

    upload._client = httpx.Client(
        transport=httpx.MockTransport(_refuse),
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

    summary = pipeline.run_once(since=date(2026, 4, 1), until=date(2026, 4, 30))

    assert pacs.fetch_calls == 0, "fetch_study must not be called on skip"
    assert pacs.query_calls == 1, "PACS query still runs — only per-study fetch is skipped"
    assert summary.total == 1
    assert summary.skipped == 1
    assert summary.uploaded == 0
    assert summary.failed == 0
    outcome = summary.outcomes[0]
    assert outcome.state == StudyState.UPLOADED
    assert outcome.reason == "already_uploaded"
    assert outcome.pseudo_study_uid is None  # not computed — short-circuited


def test_pipeline_processes_study_when_legacy_null_hash_row_exists(
    make_synthetic_study, tmp_path, monkeypatch
):
    """Regression guard. A pre-migration row with NULL hash must not skip;
    the pipeline must fetch + de-id + upload as normal on the first post-
    migration sync. (One-off cost — covered in the feature's accepted
    trade-offs.)"""
    import httpx
    from fastapi.testclient import TestClient

    from radivault_gateway.audit import AuditLogger
    from radivault_gateway.deid import DeidEngine
    from radivault_gateway.orchestrator import Pipeline
    from radivault_gateway.pacs import StudySummary
    from radivault_gateway.staging import StagingManager
    from radivault_gateway.upload import UploadClient

    monkeypatch.setenv("MOCK_CENTRAL_DUMP", str(tmp_path / "dump"))
    monkeypatch.setenv("MOCK_CENTRAL_TOKEN", "tok-abc")

    # Spin up the mock-central FastAPI app so the upload can complete.
    import radivault_mock_central.main as mod

    importlib.reload(mod)
    test_client = TestClient(mod.app)

    study_src = make_synthetic_study(n_instances=2)
    original_uid = "1.2.3.LEGACY.ROW"
    studies = [
        StudySummary(
            study_instance_uid=original_uid,
            patient_id="P-LEG",
            study_date="20260401",
            modalities_in_study=["MR"],
            num_instances=2,
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
    # Pre-seed a legacy row — UPLOADED state but NO hash (mark_state without
    # original_uid). This is the shape of the 75 pre-existing rows in Kyle's
    # production state.sqlite3.
    db.upsert_study_job("2.25.pseudo-legacy-row", state=StudyState.DEIDED)
    db.mark_state("2.25.pseudo-legacy-row", StudyState.UPLOADED)  # no original_uid

    pacs = _make_counting_pacs(studies, study_src)
    audit = AuditLogger(cfg.audit.path, gateway_id=cfg.agent.gateway_id)
    staging = StagingManager(cfg.staging.root, max_disk_pct=cfg.staging.max_disk_pct)
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=db,
        retain=cfg.deid.retain_options,
    )
    upload = UploadClient(
        "http://testserver", upload_token="tok-abc", max_retries=1, allow_insecure=True
    )

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

    assert pacs.fetch_calls == 1, (
        "legacy NULL-hash row must NOT cause skip — the pipeline must re-process"
    )
    assert summary.uploaded == 1
    assert summary.skipped == 0
    # After this run, the newly minted row (under a fresh pseudo UID) carries
    # the hash for `original_uid`, so a subsequent run WOULD skip. Verify.
    assert db.is_study_uploaded(original_uid) is True
