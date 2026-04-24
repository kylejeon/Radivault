"""End-to-end tests for ``POST /v1/ingest/studies/metadata`` (Flow A).

Runs against an in-process FastAPI app with SQLite + fakeredis + local-fs
object store so no external services are required.
"""

from __future__ import annotations

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
from radivault_central.db.models import (
    AuditIngestEvent,
    AuthToken,
    Base,
    Hospital,
    Study,
)
from radivault_central.db.session import get_engine, reset_for_tests
from radivault_central.storage.local import LocalFsObjectStore


@pytest.fixture
def built_app(tmp_path: Path) -> Iterator[tuple[TestClient, str, sessionmaker]]:
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
            hospital_id="hosp_meta",
            name="Test Hospital Meta",
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


def _manifest(
    pseudo_study_uid: str = "2.25.meta.flow-a.1",
    *,
    anonymization_flag: str = "fully_anonymized",
    n_instances: int = 17,
    total_bytes: int = 98765,
    hospital_id: str = "hosp_meta",
) -> dict:
    return {
        "manifest_version": 1,
        "gateway_id": "gw_meta",
        "hospital_id": hospital_id,
        "pseudo_study_uid": pseudo_study_uid,
        "modalities": ["CT"],
        "n_instances": n_instances,
        "total_bytes": total_bytes,
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt_version": 1,
            "method_code_sequence": ["113100"],
        },
        "anonymization_flag": anonymization_flag,
        "files": [],
        "generated_at": "2026-04-24T10:00:00Z",
    }


def _post(client: TestClient, token: str, body: dict, *, key: str | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": key or f"meta-{body['pseudo_study_uid']}",
    }
    return client.post("/v1/ingest/studies/metadata", data=json.dumps(body), headers=headers)


def test_metadata_only_happy_path(built_app):
    client, token, factory = built_app
    r = _post(client, token, _manifest())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mode"] == "metadata_only"
    assert body["job_id"].startswith("ingest_")
    # DB row landed with central_object_present=False.
    with factory() as session:
        study = session.scalar(
            select(Study).where(Study.pseudo_study_uid == "2.25.meta.flow-a.1")
        )
        assert study is not None
        assert study.central_object_present is False
        assert study.n_instances == 17
        assert study.n_series == 0
        assert study.modality == "CT"


def test_metadata_only_emits_completed_audit_event(built_app):
    client, token, factory = built_app
    r = _post(client, token, _manifest(pseudo_study_uid="2.25.meta.audit.1"))
    assert r.status_code == 201
    with factory() as session:
        events = list(
            session.scalars(
                select(AuditIngestEvent).where(
                    AuditIngestEvent.event == "central.ingest.metadata_only.completed"
                )
            ).all()
        )
        assert len(events) == 1
        assert events[0].pseudo_study_uid == "2.25.meta.audit.1"
        assert events[0].status_code == 201


def test_metadata_only_rejects_non_json_content_type(built_app):
    client, token, _ = built_app
    body = _manifest(pseudo_study_uid="2.25.meta.ctype.1")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "multipart/form-data; boundary=xyz",
        "Idempotency-Key": f"meta-{body['pseudo_study_uid']}",
    }
    r = client.post("/v1/ingest/studies/metadata", data=json.dumps(body), headers=headers)
    assert r.status_code == 415
    assert r.json()["error"] == "ERR_UNSUPPORTED_MEDIA"


def test_metadata_only_rejects_wrong_anonymization_flag(built_app):
    client, token, _ = built_app
    r = _post(
        client,
        token,
        _manifest(pseudo_study_uid="2.25.meta.anon.1", anonymization_flag="partial"),
    )
    assert r.status_code == 403
    assert r.json()["error"] == "ERR_MANIFEST_ANON"


def test_metadata_only_rejects_missing_idempotency_key(built_app):
    client, token, _ = built_app
    body = _manifest(pseudo_study_uid="2.25.meta.noidem.1")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    r = client.post("/v1/ingest/studies/metadata", data=json.dumps(body), headers=headers)
    assert r.status_code == 400
    assert r.json()["error"] == "ERR_IDEMP_MISSING"


def test_metadata_only_idempotency_replay(built_app):
    """Same Idempotency-Key returns the same response without creating a
    duplicate study row."""
    client, token, factory = built_app
    body = _manifest(pseudo_study_uid="2.25.meta.idem.1")
    key = "meta-repeat-key-0000000000000"
    first = _post(client, token, body, key=key)
    assert first.status_code == 201
    second = _post(client, token, body, key=key)
    # Middleware replays cached 2xx with ``Idempotency-Replayed`` header.
    assert second.status_code == 201
    assert second.headers.get("Idempotency-Replayed") == "true"
    # Only one Study row persisted.
    with factory() as session:
        studies = list(
            session.scalars(
                select(Study).where(Study.pseudo_study_uid == "2.25.meta.idem.1")
            ).all()
        )
        assert len(studies) == 1


def test_metadata_only_duplicate_study_on_second_key(built_app):
    """Same pseudo_study_uid with a different idempotency key still collides
    at the ``study_exists`` check."""
    client, token, _ = built_app
    body = _manifest(pseudo_study_uid="2.25.meta.dup.1")
    r1 = _post(client, token, body, key="meta-dup-first-0000000000000")
    assert r1.status_code == 201
    r2 = _post(client, token, body, key="meta-dup-second-000000000000")
    assert r2.status_code == 409
    assert r2.json()["error"] == "ERR_MANIFEST_DUP"


def test_metadata_only_hospital_mismatch_rejected(built_app):
    """Manifest's hospital_id must match token's hospital."""
    client, token, _ = built_app
    r = _post(
        client,
        token,
        _manifest(pseudo_study_uid="2.25.meta.hosp.1", hospital_id="hosp_other"),
    )
    assert r.status_code == 403
    assert r.json()["error"] == "ERR_AUTH_MISMATCH"


def test_metadata_only_no_object_storage_written(built_app, tmp_path):
    """Flow A contract: no pixel payload → no keys in object store."""
    client, token, _ = built_app
    r = _post(client, token, _manifest(pseudo_study_uid="2.25.meta.nostore.1"))
    assert r.status_code == 201
    # The LocalFsObjectStore root is in the fixture's tmp_path / "store".
    # We did not pass it explicitly so locate through app.state below.
    # Any objects-in-tree for this study_uid would indicate a wrong write.
    root = Path(client.app.state.settings.storage.local_root)
    if root.exists():
        hits = list(root.rglob("*2.25.meta.nostore.1*"))
        assert hits == []


def test_metadata_only_does_not_conflict_with_full_payload_idem_key(built_app):
    """``meta-<uid>`` and ``upload-<uid>`` are distinct idempotency keys."""
    client, token, _ = built_app
    body = _manifest(pseudo_study_uid="2.25.meta.keyns.1")
    # Use the "upload-" prefix (the convention full-payload Gateway uses) —
    # it must be accepted by the metadata endpoint too (keys are just strings
    # at the middleware layer; this test documents the non-collision).
    r_meta = _post(client, token, body, key=f"meta-{body['pseudo_study_uid']}")
    assert r_meta.status_code == 201
    # A different key for the same study still hits ERR_MANIFEST_DUP, proving
    # the dedupe is on pseudo_study_uid not on the key.
    r_full_key_same_study = _post(
        client, token, body, key=f"upload-{body['pseudo_study_uid']}"
    )
    assert r_full_key_same_study.status_code == 409
