"""End-to-end ingest + anchor against an in-process FastAPI app.

This suite does NOT require docker-compose; it uses SQLite + fakeredis + a
local-fs object store. The separate ``test_gateway_against_central`` module
covers the multi-container Docker Compose path and is marked
``@pytest.mark.integration`` (skipped unless ``CENTRAL_TEST_SERVICES=1``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from radivault_central import __version__
from radivault_central.app import create_app
from radivault_central.auth.tokens import generate_token
from radivault_central.config import Settings
from radivault_central.db.models import AuthToken, Base, Hospital
from radivault_central.db.session import get_engine, reset_for_tests
from radivault_central.storage.local import LocalFsObjectStore


@pytest.fixture
def built_app(tmp_path: Path) -> Iterator[tuple[TestClient, str, sessionmaker]]:
    reset_for_tests()
    # File-based SQLite so each engine hit sees the same data.
    db_path = tmp_path / "central.db"
    settings = Settings()
    settings.app.env = "test"
    settings.db.dsn = f"sqlite+pysqlite:///{db_path}"
    settings.storage.provider = "local"
    settings.storage.local_root = str(tmp_path / "store")
    settings.observability.log_level = "WARNING"

    # Pre-create schema + seed hospital + token before building the app so
    # create_app's internal engine (same DSN) sees the rows.
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
    # Dispose so create_app builds its own engine and hits the same file.
    engine.dispose()
    reset_for_tests()

    app = create_app(settings, testing=False)
    # Swap redis for fakeredis so nothing goes to a real Redis.
    app.state.redis = FakeStrictRedis()
    app.state.object_store = LocalFsObjectStore(settings.storage.local_root)
    for m in app.user_middleware:
        if m.cls.__name__ in {"IdempotencyMiddleware", "RateLimitMiddleware"}:
            m.kwargs["redis_client"] = app.state.redis

    with TestClient(app) as client:
        yield client, bundle.plaintext, app.state.session_factory


def _build_manifest(
    files: list[tuple[str, bytes]],
    *,
    anonymization_flag: str = "fully_anonymized",
    pseudo_study_uid: str = "2.25.test.end2end.1",
    ruleset_version: str = "v0.1.0",
    salt_version: int = 1,
    method_codes: list[str] | None = None,
) -> dict:
    files_meta = [
        {"filename": n, "sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d)} for n, d in files
    ]
    return {
        "manifest_version": 1,
        "gateway_id": "gw_test",
        "hospital_id": "hosp_test",
        "pseudo_study_uid": pseudo_study_uid,
        "modalities": ["MR"],
        "n_instances": len(files_meta),
        "total_bytes": sum(f["bytes"] for f in files_meta),
        "deid": {
            "ruleset_version": ruleset_version,
            "salt_version": salt_version,
            "method_code_sequence": method_codes or ["113100"],
        },
        "anonymization_flag": anonymization_flag,
        "files": files_meta,
        "generated_at": "2026-04-22T10:00:00Z",
    }


def _post(
    client: TestClient,
    token: str,
    manifest: dict,
    files: list[tuple[str, bytes]],
    key: str = "01HXX-TEST-KEY-0000000000000",
):
    payload = [
        ("manifest", ("manifest.json", json.dumps(manifest).encode(), "application/json")),
    ]
    for name, data in files:
        payload.append(("files", (name, data, "application/dicom")))
    return client.post(
        "/v1/ingest/studies",
        files=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )


def test_healthz_always_200(built_app):
    client, _, _ = built_app
    assert client.get("/healthz").json() == {"status": "ok"}


def test_version_endpoint_no_auth(built_app):
    client, _, _ = built_app
    r = client.get("/v1/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == __version__
    assert "api_contract_version" in body


def test_metrics_endpoint(built_app):
    client, _, _ = built_app
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"radivault_central_" in r.content


def test_ingest_auth_missing(built_app):
    client, _, _ = built_app
    r = client.post("/v1/ingest/studies", files=[("x", ("x.txt", b"", "text/plain"))])
    assert r.status_code == 401
    assert r.json()["error"] == "ERR_AUTH_MISSING"


def test_ingest_happy_path_emits_central_job_id(built_app):
    client, token, _ = built_app
    files = [("0001.dcm", b"dicom-1"), ("0002.dcm", b"dicom-2")]
    manifest = _build_manifest(files)
    r = _post(client, token, manifest, files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["central_job_id"].startswith("ingest_")
    assert body["job_id"] == body["central_job_id"]  # FR-70 hw compat
    assert body["object_keys"], "object_keys should be non-empty"


def test_ingest_rejects_missing_anonymization_flag(built_app):
    client, token, _ = built_app
    files = [("0001.dcm", b"dicom-1")]
    manifest = _build_manifest(files, anonymization_flag="pseudonymized")
    r = _post(client, token, manifest, files, key="01HX-ANON-REJECT-0000000001")
    assert r.status_code == 403
    assert r.json()["error"] == "ERR_MANIFEST_ANON"


def test_ingest_sha256_mismatch(built_app):
    client, token, _ = built_app
    files = [("0001.dcm", b"real-bytes")]
    manifest = _build_manifest(files)
    # Corrupt the declared digest.
    manifest["files"][0]["sha256"] = "0" * 64
    r = _post(client, token, manifest, files, key="01HX-SHA-MISMATCH-00000001")
    assert r.status_code == 400
    assert r.json()["error"] == "ERR_MANIFEST_SHA256"


def test_ingest_idempotency_replay(built_app):
    client, token, _ = built_app
    files = [("a.dcm", b"a-bytes")]
    manifest = _build_manifest(files, pseudo_study_uid="2.25.idem.1")
    key = "01HX-IDEM-REPLAY-000000000001"
    first = _post(client, token, manifest, files, key=key)
    assert first.status_code == 201
    second = _post(client, token, manifest, files, key=key)
    assert second.status_code == 201
    assert second.json()["central_job_id"] == first.json()["central_job_id"]
    assert second.headers.get("Idempotency-Replayed") == "true"


def test_ingest_duplicate_study_rejected(built_app):
    client, token, _ = built_app
    files = [("a.dcm", b"a-bytes")]
    manifest = _build_manifest(files, pseudo_study_uid="2.25.dup.1")
    r1 = _post(client, token, manifest, files, key="01HX-DUP-UPLOAD-00000000001")
    assert r1.status_code == 201
    r2 = _post(client, token, manifest, files, key="01HX-DUP-UPLOAD-00000000002")
    assert r2.status_code == 409
    assert r2.json()["error"] == "ERR_MANIFEST_DUP"


def test_anchor_happy_path_and_continuity(built_app):
    client, token, _ = built_app
    r = client.post(
        "/v1/audit/anchor",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "01HX-ANCHOR-0000000000000001",
        },
        json={
            "gateway_id": "gw_test",
            "seq_range": [1, 10],
            "head_hash": "0" * 64,
            "anchored_at": "2026-04-22T10:00:00Z",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["anchor_id"].startswith("anc_")

    # Non-continuous follow-up should fail.
    r2 = client.post(
        "/v1/audit/anchor",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "01HX-ANCHOR-0000000000000002",
        },
        json={
            "gateway_id": "gw_test",
            "seq_range": [20, 30],
            "head_hash": "1" * 64,
            "anchored_at": "2026-04-22T11:00:00Z",
        },
    )
    assert r2.status_code == 400
    assert r2.json()["error"] == "ERR_ANCHOR_RANGE"


def test_withdraw_stub_returns_501(built_app):
    client, token, _ = built_app
    r = client.post(
        "/v1/studies/2.25.any/withdraw-stub",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 501
    assert r.json()["error"] == "ERR_NOT_IMPLEMENTED"
