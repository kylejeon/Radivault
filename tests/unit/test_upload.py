"""Upload client + mock central ingest contract tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

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
    upload = UploadClient(
        "http://testserver", upload_token="tok-abc", max_retries=1, allow_insecure=True
    )
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


def test_post_audit_anchor_reaches_mock_central(mock_central_client, tmp_path):
    """FR-25 / AC-19: UploadClient.post_audit_anchor must deliver the head
    hash + seq range to the central ``/v1/audit/anchor`` endpoint."""

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
    upload = UploadClient(
        "http://testserver", upload_token="tok-abc", max_retries=1, allow_insecure=True
    )
    upload._client = client  # type: ignore[assignment]
    result = upload.post_audit_anchor(
        gateway_id="gw_x",
        seq_range=(0, 5),
        head_hash="sha256:" + "a" * 64,
    )
    assert result.get("anchor_id", "").startswith("anc_")
    # The mock central persists anchor requests under _anchors/.
    dump = Path(os.environ["MOCK_CENTRAL_DUMP"]) / "_anchors"
    assert dump.exists()
    stored = sorted(dump.glob("*.json"))
    assert stored, "anchor payload must be dumped by mock central"
    body = json.loads(stored[-1].read_text())
    assert body["head_hash"] == "sha256:" + "a" * 64
    assert body["seq_range"] == [0, 5]
    assert body["gateway_id"] == "gw_x"
    client.close()


def test_daemon_loop_schedules_anchor(mock_central_client, tmp_path, monkeypatch):
    """FR-25 scheduler: `start --oneshot` with short anchor interval must POST
    a head hash reflecting the local audit chain."""
    # Build minimal config pointing at mock central (via MockTransport below).
    import yaml
    from click.testing import CliRunner

    from radivault_gateway.cli.main import cli

    salt_file = tmp_path / "salt"
    salt_file.write_text("0123456789abcdef" * 2)
    cfg_data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_anchor",
            "hospital_id": "hosp_a",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": {
            "base_url": "https://pacs.example/dicom-web",
            "auth": {"type": "bearer", "token": "tok"},
            "max_concurrency": 2,
            "poll_interval_seconds": 60,
        },
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt": f"${{file:{salt_file}}}",
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
            "anchor_interval_seconds": 60,
        },
        "central": {
            "base_url": "http://testserver",
            "upload_token": "tok-abc",
            "allow_insecure": True,
        },
        "logging": {"level": "INFO", "json": True},
    }
    cfg_path = tmp_path / "gateway.yml"
    cfg_path.write_text(yaml.safe_dump(cfg_data))

    # Seed the audit log with one event so head_seq >= 0.
    from radivault_gateway.audit import AuditLogger

    seed = AuditLogger(tmp_path / "audit.log", gateway_id="gw_anchor")
    seed.append("agent.started")

    # Patch pipeline to skip PACS + upload and stub anchor to use MockTransport.
    from radivault_gateway.cli import main as cli_main

    def _bridge(request: httpx.Request) -> httpx.Response:
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

    original_build = cli_main._build_pipeline

    def _build_with_stub(cfg):
        pipeline = original_build(cfg)
        # Replace the upload client's transport with the mock central bridge.
        pipeline._upload._client = httpx.Client(
            transport=httpx.MockTransport(_bridge),
            headers={"Authorization": "Bearer tok-abc"},
            base_url="http://testserver",
        )
        # Stub PACS query to return zero studies so run_once just ticks once.
        pipeline._pacs.query_studies = lambda *a, **kw: []  # type: ignore[assignment]
        return pipeline

    monkeypatch.setattr(cli_main, "_build_pipeline", _build_with_stub)

    # Force the anchor interval check to fire on first tick by pretending the
    # last anchor was long ago: we use --oneshot so the main loop exits after
    # one iteration, which triggers the post-tick anchor branch.
    runner = CliRunner()
    r = runner.invoke(cli, ["-c", str(cfg_path), "start", "--oneshot"])
    assert r.exit_code == 0, r.output

    # Assert mock central received at least one anchor payload with our head.
    dump = Path(os.environ["MOCK_CENTRAL_DUMP"]) / "_anchors"
    assert dump.exists(), r.output
    anchors = sorted(dump.glob("*.json"))
    assert anchors, f"no anchor received. stdout: {r.output}"
    body = json.loads(anchors[-1].read_text())
    assert body["gateway_id"] == "gw_anchor"
    # head_hash should match the audit logger's latest head (one event seeded
    # plus whatever run_once appended) — at minimum, non-zero and well formed.
    assert body["head_hash"].startswith("sha256:")
    # seq_range end must be >= 0 (we seeded seq=0).
    assert body["seq_range"][1] >= 0


def test_upload_client_rejects_http_by_default():
    """H-1: plain HTTP must be refused unless allow_insecure is set."""
    with pytest.raises(ValueError) as exc:
        UploadClient("http://ingest.example", upload_token="t")
    assert "https" in str(exc.value).lower()


def test_upload_client_accepts_http_with_allow_insecure(caplog):
    """H-1: opt-in insecure mode is allowed for dev and warns on startup."""
    import logging

    caplog.set_level(logging.WARNING, logger="radivault.upload")
    client = UploadClient("http://ingest.example", upload_token="t", allow_insecure=True)
    try:
        assert client.base_url == "http://ingest.example"
        messages = [record.getMessage() for record in caplog.records]
        assert any("insecure central base_url" in m for m in messages)
    finally:
        client.close()


def test_upload_client_permanent_400_not_retried(monkeypatch, tmp_path):
    # Build a transport that always returns 400.
    def handler(request):
        return httpx.Response(400, text="invalid_manifest")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://x")
    upload = UploadClient("http://x", upload_token="t", max_retries=5, allow_insecure=True)
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
