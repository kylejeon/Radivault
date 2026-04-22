"""FR-56 audit coverage: every rejected Ingest writes one ``ingest.rejected`` row.

Round 2 QA H-3. Prior implementation only wrote ``audit_ingest_event`` on the
success path, so ``ERR_MANIFEST_ANON`` / schema / SHA-256 rejections had no
DB trace. These tests drive the router through ``TestClient`` and assert the
row lands with the right ``event`` + ``error_code`` and with no PHI columns
populated. Fixture mirrors ``test_ingest_e2e.built_app`` (file-backed SQLite)
so the router, middleware, and audit writers all see the same DB.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from radivault_central.app import create_app
from radivault_central.auth.tokens import generate_token
from radivault_central.config import Settings
from radivault_central.db.models import AuditIngestEvent, AuthToken, Base, Hospital
from radivault_central.db.session import get_engine, reset_for_tests
from radivault_central.storage.local import LocalFsObjectStore


@pytest.fixture
def audit_app(tmp_path: Path) -> Iterator[tuple[TestClient, str, sessionmaker]]:
    """Same pattern as ``test_ingest_e2e.built_app`` — file-backed SQLite so the
    app-internal engine and the test-side factory see the same rows."""
    reset_for_tests()
    db_path = tmp_path / "central.db"
    settings = Settings()
    settings.app.env = "test"
    settings.db.dsn = f"sqlite+pysqlite:///{db_path}"
    settings.storage.provider = "local"
    settings.storage.local_root = str(tmp_path / "store")
    settings.observability.log_level = "WARNING"

    engine = get_engine(settings.db.dsn, pool_size=2, max_overflow=0)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        hospital = Hospital(
            hospital_id="hosp_test",
            name="Test Hospital",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
            max_instances_per_study=5000,
            max_study_bytes=20 * 1024 * 1024 * 1024,
        )
        session.add(hospital)
        session.flush()
        bundle = generate_token()
        session.add(
            AuthToken(
                hospital_pk=hospital.hospital_pk,
                token_kid=bundle.kid,
                token_hash=bundle.hash,
            )
        )
        session.commit()
    engine.dispose()
    reset_for_tests()

    app = create_app(settings, testing=False)
    app.state.redis = FakeStrictRedis()
    app.state.object_store = LocalFsObjectStore(settings.storage.local_root)
    for m in app.user_middleware:
        if m.cls.__name__ in {"IdempotencyMiddleware", "RateLimitMiddleware"}:
            m.kwargs["redis_client"] = app.state.redis

    with TestClient(app) as client:
        yield client, bundle.plaintext, app.state.session_factory


def _build(
    *,
    pseudo_study_uid: str,
    anonymization_flag: str = "fully_anonymized",
    gateway_id: str = "gw_test",
) -> tuple[dict, list[tuple[str, bytes]]]:
    files = [("0001.dcm", b"fake-dicom-1"), ("0002.dcm", b"fake-dicom-2")]
    files_meta = [
        {"filename": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        for name, data in files
    ]
    manifest = {
        "manifest_version": 1,
        "gateway_id": gateway_id,
        "hospital_id": "hosp_test",
        "pseudo_study_uid": pseudo_study_uid,
        "modalities": ["MR"],
        "n_instances": len(files_meta),
        "total_bytes": sum(f["bytes"] for f in files_meta),
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt_version": 1,
            "method_code_sequence": ["113100"],
        },
        "anonymization_flag": anonymization_flag,
        "files": files_meta,
        "generated_at": "2026-04-22T10:00:00Z",
    }
    return manifest, files


def _post(
    client: TestClient,
    token: str,
    manifest: dict,
    files: list[tuple[str, bytes]],
    idempotency_key: str,
):
    body: list = [
        ("manifest", ("manifest.json", json.dumps(manifest).encode(), "application/json")),
    ]
    for name, data in files:
        body.append(("files", (name, data, "application/dicom")))
    return client.post(
        "/v1/ingest/studies",
        files=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
    )


def _rows(factory: sessionmaker) -> list[AuditIngestEvent]:
    with factory() as s:
        return list(s.scalars(select(AuditIngestEvent).order_by(AuditIngestEvent.event_pk)).all())


def test_rejection_missing_anonymization_flag_writes_audit_row(audit_app) -> None:
    """H-3 anchor case: FR-56 + AC-6. ``ERR_MANIFEST_ANON`` must audit."""
    client, token, factory = audit_app
    manifest, files = _build(
        pseudo_study_uid="2.25.audit.anon.1",
        anonymization_flag="pseudonymized",
    )
    resp = _post(client, token, manifest, files, "01HX-AUDIT-ANON-000000000001")
    assert resp.status_code == 403
    assert resp.json()["error"] == "ERR_MANIFEST_ANON"

    rows = _rows(factory)
    assert len(rows) == 1
    row = rows[0]
    assert row.event == "ingest.rejected"
    assert row.error_code == "ERR_MANIFEST_ANON"
    assert row.status_code == 403
    assert row.central_job_id is None
    assert row.bytes_received is None
    assert row.request_id and row.request_id != "unknown"
    # manifest parse failed at anonymization gate, so gateway_id/pseudo_study_uid
    # come from the raw-manifest best-effort peek.
    assert row.gateway_id == "gw_test"
    assert row.pseudo_study_uid == "2.25.audit.anon.1"


def test_rejection_schema_error_writes_audit_row(audit_app) -> None:
    """Invalid schema (missing required field) → ERR_MANIFEST_SCHEMA + audit row."""
    client, token, factory = audit_app
    manifest, files = _build(pseudo_study_uid="2.25.audit.schema.1")
    manifest.pop("manifest_version")  # break the schema
    resp = _post(client, token, manifest, files, "01HX-AUDIT-SCHEMA-00000000001")
    assert resp.status_code == 400
    assert resp.json()["error"] == "ERR_MANIFEST_SCHEMA"

    rows = _rows(factory)
    assert len(rows) == 1
    assert rows[0].event == "ingest.rejected"
    assert rows[0].error_code == "ERR_MANIFEST_SCHEMA"
    assert rows[0].status_code == 400
    # Raw manifest still has gateway_id field — it can be peeked.
    assert rows[0].gateway_id == "gw_test"


def test_rejection_sha256_mismatch_writes_audit_row(audit_app) -> None:
    """SHA-256 mismatch → ERR_MANIFEST_SHA256 + audit row."""
    client, token, factory = audit_app
    manifest, files = _build(pseudo_study_uid="2.25.audit.sha.1")
    manifest["files"][0]["sha256"] = "0" * 64
    resp = _post(client, token, manifest, files, "01HX-AUDIT-SHA-000000000001")
    assert resp.status_code == 400
    assert resp.json()["error"] == "ERR_MANIFEST_SHA256"

    rows = _rows(factory)
    assert len(rows) == 1
    assert rows[0].event == "ingest.rejected"
    assert rows[0].error_code == "ERR_MANIFEST_SHA256"
    # Manifest was fully parsed here, so we should have the pseudo_study_uid on record.
    assert rows[0].pseudo_study_uid == "2.25.audit.sha.1"
    assert rows[0].gateway_id == "gw_test"


def test_accepted_ingest_writes_accepted_not_rejected(audit_app) -> None:
    """Happy path keeps its ``ingest.accepted`` row — no ``ingest.rejected`` leak."""
    client, token, factory = audit_app
    manifest, files = _build(pseudo_study_uid="2.25.audit.happy.1")
    resp = _post(client, token, manifest, files, "01HX-AUDIT-HAPPY-00000000001")
    assert resp.status_code == 201, resp.text

    rows = _rows(factory)
    assert len(rows) == 1
    assert rows[0].event == "ingest.accepted"
    assert rows[0].error_code is None
    assert rows[0].status_code == 201
    assert rows[0].pseudo_study_uid == "2.25.audit.happy.1"


def test_rejection_duplicate_study_writes_audit_row(audit_app) -> None:
    """First ingest accepted; second with same pseudo_study_uid → rejected row."""
    client, token, factory = audit_app
    manifest, files = _build(pseudo_study_uid="2.25.audit.dup.1")
    first = _post(client, token, manifest, files, "01HX-AUDIT-DUP1-00000000001")
    assert first.status_code == 201, first.text

    second = _post(client, token, manifest, files, "01HX-AUDIT-DUP2-00000000002")
    assert second.status_code == 409
    assert second.json()["error"] == "ERR_MANIFEST_DUP"

    rows = _rows(factory)
    events = [r.event for r in rows]
    assert events == ["ingest.accepted", "ingest.rejected"]
    assert rows[1].error_code == "ERR_MANIFEST_DUP"
    assert rows[1].status_code == 409
