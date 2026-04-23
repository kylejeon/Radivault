"""Shared fixtures for Central Ingest tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from radivault_central.app import create_app
from radivault_central.auth.tokens import generate_token
from radivault_central.config import Settings
from radivault_central.db.models import AuthToken, Base, Hospital
from radivault_central.db.session import get_engine, reset_for_tests


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings()
    s.app.env = "test"
    s.db.dsn = "sqlite+pysqlite:///:memory:"
    s.db.migration_dsn = s.db.dsn
    s.storage.provider = "local"
    s.storage.local_root = str(tmp_path / "objects")
    s.observability.log_level = "WARNING"
    s.redis.idempotency_ttl_seconds = 60
    s.ops.max_manifest_bytes = 1_048_576
    return s


@pytest.fixture
def engine_and_factory(settings: Settings):
    reset_for_tests()
    engine = get_engine(settings.db.dsn, pool_size=2, max_overflow=0)
    Base.metadata.create_all(engine)
    factory: sessionmaker[Session] = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine, factory
    engine.dispose()
    reset_for_tests()


@pytest.fixture
def hospital(engine_and_factory) -> Hospital:
    _, factory = engine_and_factory
    with factory() as session:
        h = Hospital(
            hospital_id="hosp_test",
            name="Test Hospital",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
            max_instances_per_study=5000,
            max_study_bytes=20 * 1024 * 1024 * 1024,
        )
        session.add(h)
        session.commit()
        session.refresh(h)
        return h


@pytest.fixture
def issued_token(engine_and_factory, hospital):
    _, factory = engine_and_factory
    bundle = generate_token()
    with factory() as session:
        row = AuthToken(
            hospital_pk=hospital.hospital_pk,
            token_kid=bundle.kid,
            token_hash=bundle.hash,
        )
        session.add(row)
        session.commit()
    return bundle


@pytest.fixture
def test_app(
    settings: Settings, engine_and_factory, hospital, issued_token
) -> Iterator[TestClient]:
    # Rebuild state with the same in-memory engine.
    app = create_app(settings, testing=False)
    # Patch: use existing engine+factory (so schema + seeded hospital survive).
    engine, factory = engine_and_factory
    app.state.engine = engine
    app.state.session_factory = factory

    # Swap in fakeredis so the middleware doesn't touch the network.
    import fakeredis

    redis_client = fakeredis.FakeStrictRedis()
    app.state.redis = redis_client
    # Reconfigure middleware's bound redis (middleware holds refs from construct).
    for m in app.user_middleware:
        cls = getattr(m, "cls", None)
        if cls is None:
            continue
        if cls.__name__ in {"IdempotencyMiddleware", "RateLimitMiddleware"}:
            m.kwargs["redis_client"] = redis_client
        if cls.__name__ in {"IdempotencyMiddleware", "BearerAuthMiddleware"}:
            m.kwargs["session_factory"] = factory

    with TestClient(app) as client:
        yield client


def build_manifest(
    *,
    gateway_id: str = "gw_test",
    hospital_id: str = "hosp_test",
    pseudo_study_uid: str = "2.25.test.1",
    files: list[tuple[str, bytes]] | None = None,
    anonymization_flag: str = "fully_anonymized",
    ruleset_version: str = "v0.1.0",
    salt_version: int = 1,
    method_codes: list[str] | None = None,
) -> tuple[dict, list[tuple[str, bytes]]]:
    files = files or [("0001.dcm", b"fake-dicom-1"), ("0002.dcm", b"fake-dicom-2")]
    files_meta = [
        {"filename": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        for name, data in files
    ]
    manifest = {
        "manifest_version": 1,
        "gateway_id": gateway_id,
        "hospital_id": hospital_id,
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
    return manifest, files


def post_ingest(
    client: TestClient,
    token: str,
    manifest: dict,
    files: list[tuple[str, bytes]],
    *,
    idempotency_key: str = "01HXXX-TEST-KEY-0000000000001",
):
    payload_files = [
        ("manifest", ("manifest.json", json.dumps(manifest).encode("utf-8"), "application/json")),
    ]
    for name, data in files:
        payload_files.append(("files", (name, data, "application/dicom")))
    return client.post(
        "/v1/ingest/studies",
        files=payload_files,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
    )
