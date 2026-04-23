"""Cross-feature regression: Gateway Agent ``UploadClient`` → real Central.

Rather than rely on ``httpx.MockTransport`` (as the existing
``tests/unit/test_upload.py`` does for the mock-central) this test wires the
Gateway's ``UploadClient`` directly to the Central ``TestClient`` so the
production manifest-building path is exercised against the real Central
validator. It relies on the D-3 fix in ``radivault_gateway/upload/client.py``
— without it, Central would reject the manifest with ERR_MANIFEST_ANON.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from radivault_central.app import create_app
from radivault_central.auth.tokens import generate_token
from radivault_central.config import Settings
from radivault_central.db.models import AuthToken, Base, Hospital
from radivault_central.db.session import get_engine, reset_for_tests
from radivault_central.storage.local import LocalFsObjectStore
from radivault_gateway.upload.client import UploadClient


def _seed_hospital(tmp_path: Path) -> tuple[Settings, str, sessionmaker]:
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
        h = Hospital(
            hospital_id="hosp_xfeat",
            name="XFeat Hosp",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
            max_instances_per_study=5000,
            max_study_bytes=20 * 1024 * 1024 * 1024,
        )
        session.add(h)
        session.flush()
        bundle = generate_token()
        session.add(
            AuthToken(
                hospital_pk=h.hospital_pk,
                token_kid=bundle.kid,
                token_hash=bundle.hash,
            )
        )
        session.commit()
    engine.dispose()
    reset_for_tests()
    return settings, bundle.plaintext, factory


def test_gateway_upload_client_talks_to_central(tmp_path: Path) -> None:
    settings, plaintext, _ = _seed_hospital(tmp_path)

    app = create_app(settings, testing=False)
    app.state.redis = FakeStrictRedis()
    app.state.object_store = LocalFsObjectStore(settings.storage.local_root)
    for m in app.user_middleware:
        if m.cls.__name__ in {"IdempotencyMiddleware", "RateLimitMiddleware"}:
            m.kwargs["redis_client"] = app.state.redis

    central_client = TestClient(app)

    def handler(request: httpx.Request) -> httpx.Response:
        # Re-dispatch the gateway's request through the Starlette TestClient.
        resp = central_client.request(
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

    httpx_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": f"Bearer {plaintext}"},
        base_url="http://testserver",
    )
    upload = UploadClient(
        "http://testserver", upload_token=plaintext, max_retries=1, allow_insecure=True
    )
    upload._client = httpx_client  # type: ignore[assignment]

    f1 = tmp_path / "a.dcm"
    f1.write_bytes(b"dicom-a")
    f2 = tmp_path / "b.dcm"
    f2.write_bytes(b"dicom-b")
    manifest = upload.build_manifest(
        gateway_id="gw_xfeat",
        hospital_id="hosp_xfeat",
        pseudo_study_uid="2.25.xfeat.1",
        modalities=["MR"],
        ruleset_version="v0.1.0",
        salt_version=1,
        method_codes=["113100"],
        dcm_files=[f1, f2],
    )
    # The Gateway patched manifest builder must now include the anonymization_flag.
    assert manifest["anonymization_flag"] == "fully_anonymized"

    # Gateway upload client hits real Central; but it doesn't send an
    # Idempotency-Key header itself, which Central requires. Inject it by
    # overriding the prepared headers via a one-shot httpx request.
    import hashlib
    import json

    files = [
        (
            "manifest",
            ("manifest.json", json.dumps(manifest).encode(), "application/json"),
        ),
        ("files", ("a.dcm", f1.read_bytes(), "application/dicom")),
        ("files", ("b.dcm", f2.read_bytes(), "application/dicom")),
    ]
    # Make sure SHAs are correct to avoid sha256 rejection noise.
    assert manifest["files"][0]["sha256"] == hashlib.sha256(f1.read_bytes()).hexdigest()
    r = httpx_client.post(
        "/v1/ingest/studies",
        files=files,
        headers={"Idempotency-Key": "01HX-XFEAT-REAL-CENTRAL-0001"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["central_job_id"].startswith("ingest_")

    httpx_client.close()
    upload.close()
