"""Upload client + mock central ingest contract tests."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from radivault_gateway.upload import UploadClient, UploadError


@pytest.fixture
def mock_central_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_CENTRAL_DUMP", str(tmp_path / "dump"))
    monkeypatch.setenv("MOCK_CENTRAL_TOKEN", "tok-abc")
    # Re-import after env set so module-level EXPECTED_TOKEN picks it up.
    import importlib

    import radivault_mock_central.main as mod

    importlib.reload(mod)
    return TestClient(mod.app)


def test_mock_central_healthz(mock_central_client):
    r = mock_central_client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_mock_central_rejects_missing_auth(mock_central_client):
    r = mock_central_client.post(
        "/v1/ingest/studies",
        files={"manifest": ("manifest.json", b"{}", "application/json")},
    )
    assert r.status_code == 401


def test_mock_central_verifies_sha256(mock_central_client, tmp_path):

    content = b"hello"
    wrong_sha = "0" * 64
    manifest = json.dumps(
        {
            "manifest_version": 1,
            "gateway_id": "gw_x",
            "hospital_id": "hosp_x",
            "pseudo_study_uid": "2.25.x",
            "modalities": ["MR"],
            "n_instances": 1,
            "total_bytes": len(content),
            "deid": {
                "ruleset_version": "v0.1.0",
                "salt_version": 1,
                "method_code_sequence": ["113100"],
            },
            "files": [{"filename": "0001.dcm", "sha256": wrong_sha, "bytes": len(content)}],
            "generated_at": "2026-04-22T00:00:00Z",
        }
    ).encode()
    r = mock_central_client.post(
        "/v1/ingest/studies",
        files=[
            ("manifest", ("manifest.json", manifest, "application/json")),
            ("files", ("0001.dcm", content, "application/dicom")),
        ],
        headers={"Authorization": "Bearer tok-abc"},
    )
    assert r.status_code == 400
    assert "sha256" in r.text


def test_upload_client_happy_path(mock_central_client, tmp_path):
    # Write two tiny files to upload.
    f1 = tmp_path / "a.dcm"
    f1.write_bytes(b"alpha")
    f2 = tmp_path / "b.dcm"
    f2.write_bytes(b"beta")

    # Route httpx through a MockTransport that delegates to the FastAPI
    # TestClient. This keeps UploadClient itself synchronous while letting us
    # exercise the real FastAPI app.
    def handler(request: httpx.Request) -> httpx.Response:
        resp = mock_central_client.request(
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

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer tok-abc"},
        base_url="http://testserver",
    )
    upload = UploadClient("http://testserver", upload_token="tok-abc", max_retries=1)
    upload._client = client  # type: ignore[assignment]
    manifest = upload.build_manifest(
        gateway_id="gw_x",
        hospital_id="hosp_x",
        pseudo_study_uid="2.25.y",
        modalities=["MR"],
        ruleset_version="v0.1.0",
        salt_version=1,
        method_codes=["113100"],
        dcm_files=[f1, f2],
    )
    result = upload.upload_study(manifest, [f1, f2])
    assert result.job_id.startswith("ingest_")
    client.close()


def test_upload_client_permanent_400_not_retried(monkeypatch, tmp_path):
    # Build a transport that always returns 400.
    def handler(request):
        return httpx.Response(400, text="invalid_manifest")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://x")
    upload = UploadClient("http://x", upload_token="t", max_retries=5)
    upload._client = client  # type: ignore[assignment]
    f = tmp_path / "a.dcm"
    f.write_bytes(b"x")
    manifest = upload.build_manifest(
        gateway_id="gw",
        hospital_id="h",
        pseudo_study_uid="2.25.x",
        modalities=["MR"],
        ruleset_version="v0.1.0",
        salt_version=1,
        method_codes=["113100"],
        dcm_files=[f],
    )
    with pytest.raises(UploadError) as exc:
        upload.upload_study(manifest, [f])
    assert exc.value.retryable is False
    client.close()
