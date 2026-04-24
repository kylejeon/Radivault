"""UploadClient + Pipeline + CLI tests for metadata-only mode (Flow A).

Covers:
  - CLI: ``sync-once --metadata-only`` flag presence + wiring.
  - UploadClient.build_metadata_only_manifest shape.
  - UploadClient.upload_study_metadata_only JSON POST + idempotency key +
    happy/5xx/4xx/429 paths.
  - Pipeline.run_once(metadata_only=True) end-to-end against a stub PACS +
    stub Central.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from radivault_gateway.cli.main import cli
from radivault_gateway.upload import UploadClient, UploadError

# ---------------------------------------------------------------------------
# build_metadata_only_manifest
# ---------------------------------------------------------------------------


def test_build_metadata_only_manifest_shape():
    client = UploadClient("http://x", upload_token="t", allow_insecure=True)
    try:
        m = client.build_metadata_only_manifest(
            gateway_id="gw_a",
            hospital_id="hosp_a",
            pseudo_study_uid="2.25.meta.x",
            modalities=["MR"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            n_instances=12,
            total_bytes=34567,
        )
    finally:
        client.close()
    assert m["files"] == []
    assert m["n_instances"] == 12
    assert m["total_bytes"] == 34567
    assert m["anonymization_flag"] == "fully_anonymized"
    assert m["manifest_version"] == 1
    assert m["deid"]["method_code_sequence"] == ["113100"]


# ---------------------------------------------------------------------------
# upload_study_metadata_only — HTTP contract
# ---------------------------------------------------------------------------


def _capture_transport():
    captured: dict = {"requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["requests"].append(
            {
                "method": request.method,
                "url": str(request.url),
                "content": bytes(request.content),
                "headers": dict(request.headers),
            }
        )
        return httpx.Response(
            201,
            json={
                "job_id": "ingest_abc",
                "central_job_id": "ingest_abc",
                "mode": "metadata_only",
                "received_at": "2026-04-24T10:00:00Z",
            },
        )

    return captured, httpx.MockTransport(handler)


def test_upload_study_metadata_only_posts_json_to_metadata_path():
    captured, transport = _capture_transport()
    client = UploadClient("http://x", upload_token="t", allow_insecure=True, max_retries=1)
    try:
        client._client = httpx.Client(
            transport=transport,
            headers={"Authorization": "Bearer t"},
            base_url="http://x",
        )
        manifest = client.build_metadata_only_manifest(
            gateway_id="gw_a",
            hospital_id="hosp_a",
            pseudo_study_uid="2.25.http.1",
            modalities=["CT"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            n_instances=5,
            total_bytes=12_345,
        )
        result = client.upload_study_metadata_only(manifest)
    finally:
        client.close()
    assert result.job_id == "ingest_abc"
    # Exactly one request, JSON body, correct path + idempotency key.
    assert len(captured["requests"]) == 1
    req = captured["requests"][0]
    assert req["method"] == "POST"
    assert req["url"].endswith("/v1/ingest/studies/metadata")
    assert req["headers"].get("content-type", "").startswith("application/json")
    assert req["headers"]["idempotency-key"] == "meta-2.25.http.1"
    decoded = json.loads(req["content"])
    assert decoded["files"] == []
    assert decoded["pseudo_study_uid"] == "2.25.http.1"


def test_upload_study_metadata_only_permanent_400_not_retried():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(400, text="invalid_manifest")

    client = UploadClient("http://x", upload_token="t", allow_insecure=True, max_retries=5)
    try:
        client._client = httpx.Client(
            transport=httpx.MockTransport(handler), base_url="http://x"
        )
        manifest = client.build_metadata_only_manifest(
            gateway_id="g",
            hospital_id="h",
            pseudo_study_uid="2.25.400.1",
            modalities=["MR"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            n_instances=1,
            total_bytes=1,
        )
        with pytest.raises(UploadError) as exc:
            client.upload_study_metadata_only(manifest)
    finally:
        client.close()
    assert exc.value.retryable is False
    assert attempts["n"] == 1


def test_upload_study_metadata_only_unsupported_media_not_retried():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(415, text="unsupported")

    client = UploadClient("http://x", upload_token="t", allow_insecure=True, max_retries=5)
    try:
        client._client = httpx.Client(
            transport=httpx.MockTransport(handler), base_url="http://x"
        )
        manifest = client.build_metadata_only_manifest(
            gateway_id="g",
            hospital_id="h",
            pseudo_study_uid="2.25.415.1",
            modalities=["MR"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            n_instances=1,
            total_bytes=1,
        )
        with pytest.raises(UploadError):
            client.upload_study_metadata_only(manifest)
    finally:
        client.close()
    assert attempts["n"] == 1


def test_upload_study_metadata_only_500_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(
            201, json={"job_id": "ingest_ok", "mode": "metadata_only"}
        )

    client = UploadClient(
        "http://x",
        upload_token="t",
        allow_insecure=True,
        max_retries=3,
        retry_initial=0.0,
        retry_factor=1.0,
        retry_cap=0.0,
    )
    try:
        client._client = httpx.Client(
            transport=httpx.MockTransport(handler), base_url="http://x"
        )
        manifest = client.build_metadata_only_manifest(
            gateway_id="g",
            hospital_id="h",
            pseudo_study_uid="2.25.retry.1",
            modalities=["MR"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            n_instances=1,
            total_bytes=1,
        )
        result = client.upload_study_metadata_only(manifest)
    finally:
        client.close()
    assert calls["n"] == 2
    assert result.job_id == "ingest_ok"


# ---------------------------------------------------------------------------
# CLI: --metadata-only flag plumbing
# ---------------------------------------------------------------------------


def test_sync_once_metadata_only_flag_surfaced_in_help():
    runner = CliRunner()
    r = runner.invoke(cli, ["sync-once", "--help"])
    assert r.exit_code == 0
    assert "--metadata-only" in r.output
    # Bilingual help line per dev-spec bilingual convention.
    assert "Flow A" in r.output


# ---------------------------------------------------------------------------
# Pipeline.run_once(metadata_only=True)
# ---------------------------------------------------------------------------


class _StubPacs:
    def __init__(self, studies):
        self._studies = studies
        self.qido_calls: list[str] = []

    def query_studies(self, *a, **kw):
        return list(self._studies)

    def fetch_study_qido_summary(self, study_uid):
        """Flow A QIDO fast-path (gateway-flow-a-qido). Returns a single-row
        study summary without touching per-instance metadata."""
        from radivault_gateway.pacs.client import StudyQidoSummary

        self.qido_calls.append(study_uid)
        return StudyQidoSummary(
            study_instance_uid=study_uid,
            modalities=["CT"],
            n_instances=1,
            n_series=1,
            study_date="20240101",
            duration_ms=3,
        )

    def fetch_study(self, original_uid, fetch_dir):
        # Write a minimal DICOM file so the de-id engine has an instance to
        # process. We reuse the tiny synthetic DICOM helper below.
        fetch_dir.mkdir(parents=True, exist_ok=True)
        path = fetch_dir / "0001.dcm"
        _write_tiny_dicom(path, sop_uid="1.2.840.stub." + original_uid[-4:])

        class _Fetch:
            def __init__(self) -> None:
                self.instance_paths = [path]
                self.bytes_total = path.stat().st_size

        return _Fetch()


def _write_tiny_dicom(path: Path, *, sop_uid: str) -> None:
    """Create a DICOM file small enough to exercise the de-id engine."""
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian

    ds = FileDataset(str(path), Dataset(), file_meta=Dataset(), preamble=b"\0" * 128)
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPInstanceUID = sop_uid
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = "1.2.840.stub.study"
    ds.SeriesInstanceUID = sop_uid + ".1"
    ds.PatientID = "STUBPAT1"
    ds.PatientName = "Stub^Patient"
    ds.PatientBirthDate = "19900101"
    ds.StudyDate = "20240101"
    ds.Modality = "CT"
    ds.SeriesNumber = 1
    ds.InstanceNumber = 1
    ds.save_as(path, write_like_original=False)


@pytest.fixture
def stub_pipeline(tmp_path, monkeypatch):
    """Build a Pipeline with a stub PACS + MockTransport-backed UploadClient."""
    import yaml

    from radivault_gateway.cli import main as cli_main
    from radivault_gateway.config import load_config
    from radivault_gateway.pacs.client import StudySummary

    salt_file = tmp_path / "salt"
    salt_file.write_text("0123456789abcdef" * 2)
    cfg_data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_meta_test",
            "hospital_id": "hosp_meta_test",
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
        "audit": {"path": str(tmp_path / "audit.log")},
        "central": {
            "base_url": "http://testserver",
            "upload_token": "tok-abc",
            "allow_insecure": True,
        },
        "logging": {"level": "WARNING", "json": False},
    }
    cfg_path = tmp_path / "gateway.yml"
    cfg_path.write_text(yaml.safe_dump(cfg_data))
    cfg = load_config(str(cfg_path))

    captured: dict = {"requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["requests"].append(
            {
                "method": request.method,
                "path": request.url.path,
                "content": bytes(request.content),
                "headers": dict(request.headers),
            }
        )
        return httpx.Response(
            201,
            json={
                "job_id": "ingest_stub_ok",
                "central_job_id": "ingest_stub_ok",
                "mode": "metadata_only",
            },
        )

    pipeline = cli_main._build_pipeline(cfg)
    pipeline._upload._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer tok-abc"},
        base_url="http://testserver",
    )
    # Replace PACS with a stub returning two studies.
    study_summaries = [
        StudySummary(
            study_instance_uid="1.2.840.stub.a001",
            patient_id="STUBPAT1",
            study_date="20240101",
            modalities_in_study=["CT"],
            num_instances=1,
        ),
        StudySummary(
            study_instance_uid="1.2.840.stub.a002",
            patient_id="STUBPAT2",
            study_date="20240101",
            modalities_in_study=["CT"],
            num_instances=1,
        ),
    ]
    pipeline._pacs = _StubPacs(study_summaries)
    return pipeline, captured


def test_pipeline_metadata_only_skips_multipart_posts_json_manifest(stub_pipeline):
    pipeline, captured = stub_pipeline
    summary = pipeline.run_once(metadata_only=True, limit=2)
    assert summary.total == 2
    assert summary.uploaded == 2
    assert summary.failed == 0
    # Two requests, each JSON to the metadata endpoint with meta- key prefix.
    assert len(captured["requests"]) == 2
    for req in captured["requests"]:
        assert req["path"] == "/v1/ingest/studies/metadata"
        assert req["headers"]["content-type"].startswith("application/json")
        assert req["headers"]["idempotency-key"].startswith("meta-")
        decoded = json.loads(req["content"])
        assert decoded["files"] == []
        assert decoded["anonymization_flag"] == "fully_anonymized"
        # n_instances computed from the de-id result (1 stub instance each).
        assert decoded["n_instances"] == 1


def test_pipeline_metadata_only_dry_run_skips_upload(stub_pipeline):
    pipeline, captured = stub_pipeline
    summary = pipeline.run_once(metadata_only=True, dry_run=True, limit=1)
    assert summary.total == 1
    assert summary.uploaded == 0
    assert captured["requests"] == []


def test_pipeline_metadata_only_no_staging_final_dir_written(stub_pipeline, tmp_path):
    pipeline, _ = stub_pipeline
    pipeline.run_once(metadata_only=True, limit=1)
    staging_root = Path(pipeline._staging.root)
    # Metadata-only mode must not create any per-study final staging directory.
    # (Quarantine subdir may exist but with nothing inside.)
    hits = [p for p in staging_root.rglob("*.dcm") if "quarantine" not in str(p)]
    assert hits == []
