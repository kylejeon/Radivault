"""Pipeline behavioural tests for gateway-flow-a-qido.

Covers the three promises of the fast-path:

1. Flow A calls ``fetch_study_qido_summary`` exactly once per study and
   never touches ``fetch_study_metadata`` (WADO metadata) or ``fetch_study``
   (WADO multipart).
2. Zero disk I/O — no staging subdirectory, no tmp fetch / de-id dir.
3. The Flow A manifest has ``files=[]`` and ``total_bytes=0``; Central
   receives a single JSON POST to ``/v1/ingest/studies/metadata``.
4. The skip short-circuit still runs: when ``is_study_uploaded`` returns
   True, QIDO itself is never called.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from radivault_gateway.pacs.client import StudyQidoSummary, StudySummary
from radivault_gateway.state import StudyState


class _FlowAPacs:
    """Flow A stub: supports QIDO + raises on any WADO-style call."""

    def __init__(self, studies):
        self._studies = studies
        self.query_calls = 0
        self.qido_calls: list[str] = []

    def query_studies(self, *a, **kw):
        self.query_calls += 1
        return list(self._studies)

    def fetch_study_qido_summary(self, study_uid):
        self.qido_calls.append(study_uid)
        return StudyQidoSummary(
            study_instance_uid=study_uid,
            modalities=["CT"],
            n_instances=192,
            n_series=3,
            study_date="20240101",
            duration_ms=3,
        )

    def fetch_study_metadata(self, study_uid, out_dir):  # pragma: no cover
        raise AssertionError(
            "fetch_study_metadata must not be called — Flow A uses QIDO fast-path"
        )

    def fetch_study(self, study_uid, out_dir):  # pragma: no cover
        raise AssertionError(
            "fetch_study is Flow B — must not be called in metadata_only mode"
        )


def _build_pipeline(tmp_path, studies):
    """Build a Pipeline with a MockTransport-backed UploadClient and a
    Flow A PACS stub. Keeps every expensive v0.2 stage disabled."""
    import yaml

    from radivault_gateway.cli import main as cli_main
    from radivault_gateway.config import load_config

    salt_file = tmp_path / "salt"
    salt_file.write_text("0123456789abcdef" * 2)
    cfg_data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_flow_a",
            "hospital_id": "hosp_flow_a",
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
                "job_id": "ingest_flow_a_ok",
                "central_job_id": "ingest_flow_a_ok",
                "mode": "metadata_only",
            },
        )

    pipeline = cli_main._build_pipeline(cfg)
    pipeline._upload._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer tok-abc"},
        base_url="http://testserver",
    )
    pipeline._pacs = _FlowAPacs(studies)
    return pipeline, captured


def _make_summary(uid: str) -> StudySummary:
    return StudySummary(
        study_instance_uid=uid,
        patient_id="PAT",
        study_date="20240101",
        modalities_in_study=["CT"],
        num_instances=192,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_flow_a_calls_only_qido_and_skips_wado(tmp_path):
    summaries = [_make_summary("1.2.840.flow_a.1"), _make_summary("1.2.840.flow_a.2")]
    pipeline, captured = _build_pipeline(tmp_path, summaries)
    run = pipeline.run_once(metadata_only=True, limit=2)

    assert run.total == 2
    assert run.uploaded == 2
    assert run.failed == 0
    assert pipeline._pacs.qido_calls == ["1.2.840.flow_a.1", "1.2.840.flow_a.2"]
    # Two Flow A manifest POSTs, exactly — no multipart uploads.
    assert len(captured["requests"]) == 2
    for req in captured["requests"]:
        assert req["method"] == "POST"
        assert req["path"] == "/v1/ingest/studies/metadata"
        assert req["headers"]["content-type"].startswith("application/json")
        assert req["headers"]["idempotency-key"].startswith("meta-")
        body = json.loads(req["content"])
        assert body["files"] == []
        assert body["total_bytes"] == 0
        # n_instances must carry the QIDO counter through to the manifest.
        assert body["n_instances"] == 192
        assert body["modalities"] == ["CT"]
        # Static Flow A method code declaration (PS3.15 Annex E Basic).
        assert body["deid"]["method_code_sequence"] == ["113100"]


def test_flow_a_writes_no_staging_files(tmp_path):
    summaries = [_make_summary("1.2.840.flow_a.io")]
    pipeline, _ = _build_pipeline(tmp_path, summaries)
    pipeline.run_once(metadata_only=True, limit=1)

    staging_root = Path(pipeline._staging.root)
    # Flow A must not materialise any .dcm anywhere under staging.
    # (Quarantine subdir is allowed to exist but must stay empty.)
    hits = [p for p in staging_root.rglob("*.dcm") if "quarantine" not in str(p)]
    assert hits == []
    # There must also be no per-study staging directory — the QIDO fast-path
    # never calls ``ensure_study_dir``.
    non_quarantine = [
        p for p in staging_root.iterdir() if p.is_dir() and p.name != "quarantine"
    ]
    assert non_quarantine == []


def test_flow_a_marks_study_uploaded_with_original_hash(tmp_path):
    """The UPLOADED mark must carry ``original_uid`` so a subsequent sync
    short-circuits via ``is_study_uploaded``."""
    summaries = [_make_summary("1.2.840.flow_a.skip_next")]
    pipeline, _ = _build_pipeline(tmp_path, summaries)
    pipeline.run_once(metadata_only=True, limit=1)

    # After the Flow A upload, a second sync of the same study must skip.
    assert pipeline._db.is_study_uploaded("1.2.840.flow_a.skip_next") is True


# ---------------------------------------------------------------------------
# Skip interaction — already-uploaded studies do not touch QIDO
# ---------------------------------------------------------------------------


def test_flow_a_skip_does_not_call_qido(tmp_path):
    """When the state DB already records the study as UPLOADED, the
    pipeline must short-circuit BEFORE calling QIDO. Otherwise we still
    waste one network round-trip per already-seen study."""
    original_uid = "1.2.840.flow_a.already_done"
    summaries = [_make_summary(original_uid)]
    pipeline, captured = _build_pipeline(tmp_path, summaries)

    # Pre-seed an UPLOADED row with the hash for original_uid.
    pipeline._db.upsert_study_job("2.25.pre-seeded", state=StudyState.DEIDED)
    pipeline._db.mark_state(
        "2.25.pre-seeded", StudyState.UPLOADED, original_uid=original_uid
    )

    run = pipeline.run_once(metadata_only=True, limit=1)

    # One cycle, zero QIDO calls, zero uploads. Summary rolls to skipped.
    assert pipeline._pacs.qido_calls == []
    assert captured["requests"] == []
    assert run.total == 1
    assert run.skipped == 1
    assert run.uploaded == 0


# ---------------------------------------------------------------------------
# Failure modes — PacsError + UploadError — do not leak tmp dirs
# ---------------------------------------------------------------------------


def test_flow_a_pacs_error_marks_failed_fetch(tmp_path):
    from radivault_gateway.pacs import PacsError

    class _FailingPacs(_FlowAPacs):
        def fetch_study_qido_summary(self, study_uid):  # type: ignore[override]
            raise PacsError("upstream offline", status_code=502)

    summaries = [_make_summary("1.2.840.flow_a.fail.1")]
    pipeline, captured = _build_pipeline(tmp_path, summaries)
    pipeline._pacs = _FailingPacs(summaries)

    run = pipeline.run_once(metadata_only=True, limit=1)

    assert run.total == 1
    assert run.failed == 1
    assert run.uploaded == 0
    assert captured["requests"] == []  # no upload attempted on fetch failure
    outcome = run.outcomes[0]
    assert outcome.state == StudyState.FAILED_FETCH


def test_flow_a_dry_run_does_not_upload(tmp_path):
    summaries = [_make_summary("1.2.840.flow_a.dry")]
    pipeline, captured = _build_pipeline(tmp_path, summaries)
    run = pipeline.run_once(metadata_only=True, dry_run=True, limit=1)

    # QIDO still runs (we need the counters for the audit trail / logs),
    # but the manifest POST must be skipped.
    assert pipeline._pacs.qido_calls == ["1.2.840.flow_a.dry"]
    assert captured["requests"] == []
    assert run.outcomes[0].state == StudyState.DEIDED
    assert run.outcomes[0].reason == "dry_run"


def test_flow_a_prefers_qido_modalities_over_query_summary(tmp_path):
    """QIDO's per-study modalities are authoritative; when present they
    override the bulk-list ``query_studies`` snapshot."""

    class _RichQido(_FlowAPacs):
        def fetch_study_qido_summary(self, study_uid):  # type: ignore[override]
            self.qido_calls.append(study_uid)
            return StudyQidoSummary(
                study_instance_uid=study_uid,
                modalities=["MR", "CT"],  # differs from query_studies (CT only)
                n_instances=10,
                n_series=2,
                study_date="20240101",
                duration_ms=4,
            )

    summaries = [_make_summary("1.2.840.flow_a.mods")]
    pipeline, captured = _build_pipeline(tmp_path, summaries)
    pipeline._pacs = _RichQido(summaries)

    pipeline.run_once(metadata_only=True, limit=1)
    body = json.loads(captured["requests"][0]["content"])
    assert body["modalities"] == ["MR", "CT"]
    assert body["n_instances"] == 10


def test_flow_a_falls_back_to_query_modalities_when_qido_empty(tmp_path):
    """Some PACS omit ModalitiesInStudy on the per-study row. The pipeline
    falls back to the bulk-list value so the manifest isn't empty."""

    class _BareQido(_FlowAPacs):
        def fetch_study_qido_summary(self, study_uid):  # type: ignore[override]
            self.qido_calls.append(study_uid)
            return StudyQidoSummary(
                study_instance_uid=study_uid,
                modalities=[],  # PACS omitted the tag
                n_instances=1,
                n_series=1,
                study_date="20240101",
                duration_ms=4,
            )

    summaries = [
        StudySummary(
            study_instance_uid="1.2.840.flow_a.bare",
            patient_id="PAT",
            study_date="20240101",
            modalities_in_study=["NM"],
            num_instances=1,
        )
    ]
    pipeline, captured = _build_pipeline(tmp_path, summaries)
    pipeline._pacs = _BareQido(summaries)

    pipeline.run_once(metadata_only=True, limit=1)
    body = json.loads(captured["requests"][0]["content"])
    assert body["modalities"] == ["NM"]  # from the query_studies summary


def test_flow_a_unknown_ruleset_marks_failed_deid(tmp_path):
    """``resolve_flow_a_method_codes`` raises on unknown rulesets. The
    pipeline must surface the failure as ``FAILED_DEID`` so the sync loop
    continues with other studies rather than aborting the whole run."""
    summaries = [_make_summary("1.2.840.flow_a.bad_ruleset")]
    pipeline, captured = _build_pipeline(tmp_path, summaries)
    # Swap in an unregistered ruleset version. The config object is a dataclass
    # so we mutate the nested attribute in place.
    pipeline._cfg.deid.ruleset_version = "v0.99.nope"

    run = pipeline.run_once(metadata_only=True, limit=1)

    assert run.failed == 1
    assert run.uploaded == 0
    assert captured["requests"] == []
    assert run.outcomes[0].state == StudyState.FAILED_DEID
