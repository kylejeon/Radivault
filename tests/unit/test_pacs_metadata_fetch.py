"""Tests for Flow A PACS metadata fetch.

Covers:
  - ``dicom_json.json_to_dataset`` / ``json_to_datasets`` conversion including
    group-0002 split-out, BulkDataURI drop, and defensive skipping of
    malformed items.
  - ``DicomWebPacsClient.fetch_study_metadata`` HTTP contract — path,
    ``Accept`` header, 204 empty response, non-JSON body rejection, 5xx
    retry bookkeeping reuse.
  - Pipeline integration: when ``metadata_only=True`` and the PACS stub
    exposes ``fetch_study_metadata``, the orchestrator prefers the metadata
    path and never touches ``fetch_study``. The de-ID engine processes the
    synthesized Part-10 files without raising on the missing ``PixelData``.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import httpx
import pydicom
import pytest

from radivault_gateway.pacs import (
    DicomWebPacsClient,
    PacsError,
    json_to_dataset,
    json_to_datasets,
    write_datasets_to_dir,
)


# DICOM JSON PS3.18 §F fixtures — keep them close to real Orthanc responses.
def _sample_json(
    *,
    sop_uid: str = "1.2.840.1234.5.6.7",
    study_uid: str = "1.2.840.1234.5.6",
    series_uid: str = "1.2.840.1234.5.6.5",
    patient_id: str = "PAT1",
    patient_name: str = "DOE^JANE",
    burned: str = "NO",
    modality: str = "CT",
    with_pixel_bulk: bool = True,
) -> dict[str, Any]:
    j: dict[str, Any] = {
        "00020010": {"vr": "UI", "Value": ["1.2.840.10008.1.2.1"]},
        "00080016": {"vr": "UI", "Value": ["1.2.840.10008.5.1.4.1.1.2"]},
        "00080018": {"vr": "UI", "Value": [sop_uid]},
        "0020000D": {"vr": "UI", "Value": [study_uid]},
        "0020000E": {"vr": "UI", "Value": [series_uid]},
        "00100020": {"vr": "LO", "Value": [patient_id]},
        "00100010": {"vr": "PN", "Value": [{"Alphabetic": patient_name}]},
        "00080060": {"vr": "CS", "Value": [modality]},
        "00280301": {"vr": "CS", "Value": [burned]},
        "00080020": {"vr": "DA", "Value": ["20240101"]},
    }
    if with_pixel_bulk:
        j["7FE00010"] = {"vr": "OB", "BulkDataURI": "http://orthanc/bulk/abc"}
    return j


# ---------------------------------------------------------------------------
# json_to_dataset / json_to_datasets
# ---------------------------------------------------------------------------


def test_json_to_dataset_extracts_core_fields_and_drops_pixel_data():
    ds = json_to_dataset(_sample_json())
    assert ds.PatientID == "PAT1"
    assert ds.Modality == "CT"
    # BulkDataURI references must be resolved to nothing — PixelData absent.
    assert "PixelData" not in ds
    # file_meta promotion: group 0002 elements live on ds.file_meta now.
    assert ds.file_meta.TransferSyntaxUID == "1.2.840.10008.1.2.1"
    assert ds.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID


def test_json_to_dataset_backfills_missing_file_meta():
    payload = _sample_json()
    del payload["00020010"]  # strip TransferSyntax
    ds = json_to_dataset(payload)
    # Falls back to ExplicitVRLittleEndian per helper contract.
    assert str(ds.file_meta.TransferSyntaxUID) == "1.2.840.10008.1.2.1"
    # MediaStorageSOPClassUID is backfilled from SOPClassUID when absent.
    assert ds.file_meta.MediaStorageSOPClassUID == "1.2.840.10008.5.1.4.1.1.2"


def test_json_to_datasets_skips_malformed_items(caplog):
    good = _sample_json(sop_uid="1.2.840.1234.1", with_pixel_bulk=False)
    bad = {"not": "a valid dicom json instance"}
    with caplog.at_level("WARNING"):
        datasets = json_to_datasets([good, bad])
    # Only the well-formed instance survives; the helper does not raise.
    assert len(datasets) == 1
    assert datasets[0].PatientID == "PAT1"


def test_write_datasets_to_dir_roundtrips_via_dcmread(tmp_path):
    datasets = json_to_datasets(
        [
            _sample_json(sop_uid="1.2.840.1234.1"),
            _sample_json(sop_uid="1.2.840.1234.2"),
        ]
    )
    paths, total_bytes = write_datasets_to_dir(datasets, tmp_path)
    assert len(paths) == 2
    assert total_bytes > 0
    # Re-reading the Part-10 files with pydicom must succeed without force=True.
    ds = pydicom.dcmread(paths[0], force=False)
    assert ds.PatientID == "PAT1"
    assert "PixelData" not in ds


# ---------------------------------------------------------------------------
# DicomWebPacsClient.fetch_study_metadata — HTTP contract
# ---------------------------------------------------------------------------


def _make_client(handler) -> DicomWebPacsClient:
    client = DicomWebPacsClient(
        "http://pacs.example/dicom-web",
        auth_type="bearer",
        token="tok",
        max_retries=1,
        retry_initial=0.0,
        retry_factor=1.0,
        retry_cap=0.0,
    )
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/dicom+json", "Authorization": "Bearer tok"},
    )
    return client


def test_fetch_study_metadata_happy_path_writes_part10_files(tmp_path):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["accept"] = request.headers.get("accept", "")
        body = [
            _sample_json(sop_uid="1.2.840.fetch.a1"),
            _sample_json(sop_uid="1.2.840.fetch.a2"),
        ]
        return httpx.Response(200, json=body)

    client = _make_client(handler)
    try:
        result = client.fetch_study_metadata("1.2.840.study.xyz", tmp_path)
    finally:
        client.close()
    # URL must hit the metadata sub-resource (PS3.18 §10.4), not /studies/{uid}.
    assert "/studies/1.2.840.study.xyz/metadata" in captured["url"]
    assert captured["accept"].startswith("application/dicom+json")
    assert len(result.instance_paths) == 2
    assert result.bytes_total > 0
    # Files must round-trip via dcmread without force=True.
    ds = pydicom.dcmread(result.instance_paths[0], force=False)
    assert ds.Modality == "CT"
    assert "PixelData" not in ds


def test_fetch_study_metadata_empty_204_returns_zero_instances(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = _make_client(handler)
    try:
        result = client.fetch_study_metadata("1.2.840.empty", tmp_path)
    finally:
        client.close()
    assert result.instance_paths == []
    assert result.bytes_total == 0


def test_fetch_study_metadata_non_array_body_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "an array"})

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError) as exc:
            client.fetch_study_metadata("1.2.840.bad", tmp_path)
    finally:
        client.close()
    assert "expected JSON array" in str(exc.value)


def test_fetch_study_metadata_error_status_raises_pacserror(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="study_not_found")

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError) as exc:
            client.fetch_study_metadata("1.2.840.missing", tmp_path)
    finally:
        client.close()
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Pipeline integration — metadata_only uses the QIDO fast-path
# (gateway-flow-a-qido). The legacy ``fetch_study_metadata`` path is retained
# for debug but never invoked by the orchestrator in metadata-only mode.
# ---------------------------------------------------------------------------


class _MetadataPacsStub:
    """PACS stub that records which fetch method the orchestrator picked.

    ``fetch_study_qido_summary`` is the Flow A call (gateway-flow-a-qido).
    ``fetch_study_metadata`` + ``fetch_study`` are recorded so regressions
    that reintroduce a WADO pull are caught.
    """

    def __init__(self, studies):
        self._studies = studies
        self.qido_calls: list[str] = []
        self.metadata_calls: list[str] = []
        self.full_calls: list[str] = []

    def query_studies(self, *a, **kw):
        return list(self._studies)

    def fetch_study_qido_summary(self, study_uid):
        """Flow A fast-path. Returns study-level counters without any
        per-instance I/O — matches the real QIDO response contract."""
        from radivault_gateway.pacs.client import StudyQidoSummary

        self.qido_calls.append(study_uid)
        return StudyQidoSummary(
            study_instance_uid=study_uid,
            modalities=["CT"],
            n_instances=1,
            n_series=1,
            study_date="20240101",
            duration_ms=5,
        )

    def fetch_study_metadata(self, study_uid, out_dir):  # pragma: no cover
        # The Flow A QIDO fast-path replaced this call. A regression that
        # re-enables it would show up here.
        self.metadata_calls.append(study_uid)
        raise AssertionError(
            "fetch_study_metadata must not be invoked — Flow A uses QIDO"
        )

    def fetch_study(self, study_uid, out_dir):  # pragma: no cover
        # If the orchestrator ever calls this branch in metadata_only=True
        # mode, the test below will fail — which is the contract we want.
        self.full_calls.append(study_uid)
        raise AssertionError("fetch_study must not be invoked in metadata_only mode")


@pytest.fixture
def metadata_pipeline(tmp_path):
    import yaml

    from radivault_gateway.cli import main as cli_main
    from radivault_gateway.config import load_config
    from radivault_gateway.pacs.client import StudySummary

    salt_file = tmp_path / "salt"
    salt_file.write_text("0123456789abcdef" * 2)
    cfg_data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_meta_fetch",
            "hospital_id": "hosp_meta_fetch",
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
        captured["requests"].append({"path": request.url.path})
        return httpx.Response(
            201,
            json={"job_id": "ingest_stub_ok", "central_job_id": "ingest_stub_ok"},
        )

    pipeline = cli_main._build_pipeline(cfg)
    pipeline._upload._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer tok-abc"},
        base_url="http://testserver",
    )
    summaries = [
        StudySummary(
            study_instance_uid="1.2.840.stub.m01",
            patient_id="PAT1",
            study_date="20240101",
            modalities_in_study=["CT"],
            num_instances=1,
        ),
        StudySummary(
            study_instance_uid="1.2.840.stub.m02",
            patient_id="PAT2",
            study_date="20240101",
            modalities_in_study=["CT"],
            num_instances=1,
        ),
    ]
    pacs_stub = _MetadataPacsStub(summaries)
    pipeline._pacs = pacs_stub
    return pipeline, pacs_stub, captured


def test_pipeline_metadata_only_uses_qido_fast_path(metadata_pipeline):
    """gateway-flow-a-qido: Flow A must use ``fetch_study_qido_summary`` and
    must NOT invoke either ``fetch_study_metadata`` (WADO metadata) or
    ``fetch_study`` (full multipart WADO). The QIDO call returns kilobyte-
    scale counters in ~0.25 s vs ~14 s for a per-instance metadata pull on
    a 192-slice CT — the fast-path is the entire point of the feature.
    """
    pipeline, pacs_stub, captured = metadata_pipeline
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # pydicom emits UI-validation warnings on the synthetic UIDs
        summary = pipeline.run_once(metadata_only=True, limit=2)
    assert summary.total == 2
    assert summary.uploaded == 2
    assert summary.failed == 0
    # The orchestrator must have exclusively used the QIDO summary call.
    assert pacs_stub.qido_calls == ["1.2.840.stub.m01", "1.2.840.stub.m02"]
    assert pacs_stub.metadata_calls == []
    assert pacs_stub.full_calls == []
    # Central received the two JSON manifest POSTs on the Flow A endpoint.
    assert len(captured["requests"]) == 2
    for req in captured["requests"]:
        assert req["path"] == "/v1/ingest/studies/metadata"


def test_pipeline_full_payload_unchanged_when_metadata_only_false(metadata_pipeline):
    """Regression guard: without --metadata-only, the orchestrator must NOT
    touch either ``fetch_study_metadata`` or ``fetch_study_qido_summary``.
    Flow B (order fulfillment) depends on ``fetch_study`` remaining the
    default code path.
    """
    pipeline, pacs_stub, _ = metadata_pipeline

    # Swap in a second stub that raises if any Flow A method is invoked.
    class _FullPayloadOnlyStub:
        def __init__(self, studies):
            self._studies = studies
            self.full_calls: list[str] = []

        def query_studies(self, *a, **kw):
            return list(self._studies)

        def fetch_study(self, study_uid, out_dir):
            self.full_calls.append(study_uid)
            # Return an empty fetch — de-id will raise FileNotFoundError and
            # the study will be marked failed_deid. That is fine for this
            # regression check: we only care about which method was called.
            Path(out_dir).mkdir(parents=True, exist_ok=True)

            class _Fetch:
                def __init__(self) -> None:
                    self.instance_paths: list[Path] = []
                    self.bytes_total = 0

            return _Fetch()

        def fetch_study_metadata(self, study_uid, out_dir):  # pragma: no cover
            raise AssertionError(
                "fetch_study_metadata must not be called in full-payload mode"
            )

        def fetch_study_qido_summary(self, study_uid):  # pragma: no cover
            raise AssertionError(
                "fetch_study_qido_summary is a Flow A call — not expected in Flow B"
            )

    from radivault_gateway.pacs.client import StudySummary

    summaries = [
        StudySummary(
            study_instance_uid="1.2.840.stub.full01",
            patient_id="PAT1",
            study_date="20240101",
            modalities_in_study=["CT"],
            num_instances=1,
        ),
    ]
    stub = _FullPayloadOnlyStub(summaries)
    pipeline._pacs = stub
    # metadata_only=False (default). Should hit fetch_study, not metadata.
    pipeline.run_once(limit=1)
    assert stub.full_calls == ["1.2.840.stub.full01"]


def test_pipeline_flow_a_does_not_inspect_burnin_annotation(metadata_pipeline):
    """Flow A semantic change (gateway-flow-a-qido): burn-in detection is
    deferred to Flow B.

    Flow A no longer pulls per-instance tags (BurnedInAnnotation lives on
    each instance), so a burn-in=YES study will upload to Central as a
    metadata-only record. Actual pixel inspection + quarantine happens at
    order-fulfillment time (Flow B) when pixels are materialised.

    This is acceptable because the Flow A manifest does not transfer any
    pixel data — there is no PHI exposure from the metadata-only upload.
    """
    pipeline, _, captured = metadata_pipeline
    # The stub already returns the same QIDO counters for every UID; we
    # simply assert that a study whose original instance *would* have
    # burn-in=YES still uploads successfully in Flow A. This is the exact
    # opposite of the old WADO-metadata path, which would have quarantined.
    from radivault_gateway.pacs.client import StudySummary

    class _BurnedInStub(_MetadataPacsStub):
        """Tagged subclass — same QIDO response, different test intent."""

    pipeline._pacs = _BurnedInStub(
        [
            StudySummary(
                study_instance_uid="1.2.840.stub.burn01",
                patient_id="PAT1",
                study_date="20240101",
                modalities_in_study=["CT"],
                num_instances=1,
            )
        ]
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        summary = pipeline.run_once(metadata_only=True, limit=1)
    assert summary.total == 1
    # Burn-in detection moved to Flow B; Flow A uploads without inspection.
    assert summary.uploaded == 1
    assert summary.quarantined == 0
    # Central recorded exactly one Flow A manifest POST.
    assert len(captured["requests"]) == 1
    assert captured["requests"][0]["path"] == "/v1/ingest/studies/metadata"
