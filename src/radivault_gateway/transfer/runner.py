"""Adapter that turns a transfer-job claim into PACS fetch + De-ID + upload.

v0.1 keeps the real PACS/De-ID/upload wiring pluggable so the gateway
package doesn't grow coupling with the fulfilment subsystem. The CLI
wires the default ``mock_runner`` (for ``transfer test`` smoke runs);
production deployments swap in the real pipeline.

jpg-preview-defacing FR-PREVIEW-1: the optional ``preview_runner``
hook below runs *between* the real upload runner and the central-side
``complete`` RPC. It is a thin pass-through shim — when the flag is
off, ``process_study`` returns ``skipped=True`` instantly so the cost
on existing pipeline runs is one env-var read.

B-1 wiring (this commit) — :func:`with_preview_pipeline` wraps any
upstream runner so ``process_study`` is invoked once per study from
the resulting manifest, and the per-study :class:`PreviewBatchResult`
is merged into ``manifest_entry["preview"]`` via
:func:`merge_preview_into_manifest`. The wrapper short-circuits to
the original runner output when ``PREVIEW_PIPELINE_ENABLED != true``
so legacy ingestion is bit-for-bit unaffected.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from typing import Any, Protocol

from radivault_gateway.preview_pipeline import (
    AuditWriter,
    FrameWriter,
    MinioClient,
    PreviewBatchResult,
    SeriesInput,
    is_pipeline_enabled,
    process_study,
)
from radivault_gateway.transfer.claim import Claim
from radivault_gateway.transfer.consumer import JobResult
from radivault_gateway.transfer.progress import ProgressReporter

log = logging.getLogger("radivault_gateway.transfer.runner")


def mock_runner(claim: Claim, reporter: ProgressReporter) -> JobResult:
    """Pretend to fetch + de-id + upload every study. Useful for tests
    and ``gateway-agent transfer test``."""
    manifest: list[dict[str, Any]] = []
    for study in claim.studies:
        reporter.record(fetched=1, deided=1, uploaded=1)
        manifest.append(
            {
                "pseudo_study_uid": study["pseudo_study_uid"],
                "n_instances": study.get("expected_instances", 0),
                "total_bytes": 0,
                "status": "uploaded",
                "central_job_ids": [f"mock_ingest_{study['pseudo_study_uid']}"],
            }
        )
    return JobResult(ok=True, manifest=manifest)


def build_runner(
    *, upload_fn: Callable[[Claim, ProgressReporter], JobResult] | None = None
) -> Callable[[Claim, ProgressReporter], JobResult]:
    """Return the configured runner — falls back to :func:`mock_runner`."""
    return upload_fn or mock_runner


# ---------------------------------------------------------------------------
# B-1 — preview_pipeline wiring
# ---------------------------------------------------------------------------


class SeriesInputsProvider(Protocol):
    """Strategy that maps a (claim, manifest_entry) tuple to the
    De-ID'd series inputs that ``process_study`` will iterate over.

    Production wiring (FR-PREVIEW-2) supplies a function backed by the
    on-disk staging dir + DICOM extract metadata. The mock_runner test
    path supplies an empty list (no series → ``process_study`` returns
    a result with ``series=[]`` but still emits a manifest.preview
    block so central can route the v2.2 schema codepath.
    """

    def __call__(
        self, *, claim: Claim, manifest_entry: dict[str, Any]
    ) -> list[SeriesInput]: ...


def _empty_series_inputs(*, claim: Claim, manifest_entry: dict[str, Any]) -> list[SeriesInput]:
    """Default provider — emits no series. Suitable for the demo
    ``mock_runner`` and unit tests; production runners override."""
    return []


def with_preview_pipeline(
    upstream: Callable[[Claim, ProgressReporter], JobResult],
    *,
    minio_client: MinioClient,
    audit_writer: AuditWriter,
    frame_writer: FrameWriter,
    series_inputs_provider: SeriesInputsProvider | None = None,
    flag_check: Callable[[], bool] = is_pipeline_enabled,
) -> Callable[[Claim, ProgressReporter], JobResult]:
    """Wrap ``upstream`` so the preview pipeline runs after every study.

    Behaviour matrix (FR-PREVIEW-3):

      * ``PREVIEW_PIPELINE_ENABLED != true``        → upstream() result
        is returned verbatim.
      * Flag on, upstream returned ``ok=False``     → upstream() result
        is returned verbatim (we don't run preview on failed jobs).
      * Flag on, upstream returned ``ok=True``      → for each study in
        the manifest we call :func:`process_study` and merge the
        :class:`PreviewBatchResult` into ``entry["preview"]``.
    """
    provider = series_inputs_provider or _empty_series_inputs

    def _runner(claim: Claim, reporter: ProgressReporter) -> JobResult:
        result = upstream(claim, reporter)
        if not flag_check():
            return result
        if not result.ok:
            return result

        preview_results_by_study: dict[str, dict[str, Any]] = {}
        for entry in result.manifest:
            if not isinstance(entry, dict):
                continue
            uid = entry.get("pseudo_study_uid")
            if not uid:
                continue
            try:
                series_inputs = provider(claim=claim, manifest_entry=entry)
            except Exception as exc:  # noqa: BLE001
                # A provider failure must NOT crash the gateway pipeline
                # (FR-DEFACE-8 invariant). Skip preview for this study;
                # central just sees no preview block (legacy backward-compat).
                log.warning(
                    "preview_provider_failed",
                    extra={
                        "event": "preview.provider.error",
                        "pseudo_study_uid": uid,
                        "error": str(exc)[:200],
                    },
                )
                continue
            try:
                batch: PreviewBatchResult = process_study(
                    pseudo_study_uid=uid,
                    series_inputs=series_inputs,
                    study_description=entry.get("study_description"),
                    minio_client=minio_client,
                    audit_writer=audit_writer,
                    frame_writer=frame_writer,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception(
                    "preview_process_study_crashed",
                    extra={
                        "event": "preview.process.error",
                        "pseudo_study_uid": uid,
                        "error": str(exc)[:200],
                    },
                )
                continue
            preview_results_by_study[uid] = _preview_to_dict(batch)

        if not preview_results_by_study:
            return result
        return merge_preview_into_manifest(
            result, preview_results_by_study=preview_results_by_study
        )

    return _runner


def _preview_to_dict(batch: PreviewBatchResult) -> dict[str, Any]:
    """Render a :class:`PreviewBatchResult` into a JSON-friendly dict
    that matches ``radivault_central.manifest.schema.PreviewBatch``.

    The pydantic model on the central side accepts ``extra="allow"``
    so we can ship the dict verbatim.
    """
    return {
        "skipped": batch.skipped,
        "reason": batch.reason,
        "pipeline_version": batch.pipeline_version,
        "series": [
            {
                "pseudo_series_uid": s.pseudo_series_uid,
                "series_num": s.series_num,
                "modality": s.modality,
                "body_part": s.body_part,
                "preview_status": s.preview_status,
                "deface_decision": s.deface_decision,
                "deface_decision_reason": s.deface_decision_reason,
                "phi_scrub_method": s.phi_scrub_method,
                "frame_count": s.frame_count,
                "frames": [dataclasses.asdict(f) for f in s.frames],
                "outcome": _outcome_for(s),
                "error_code": s.error_code,
                # error_detail intentionally omitted from the dict shim;
                # the central-side _scrub_audit_error_detail guard would
                # redact most strings anyway. The audit row preserves
                # error_code for diagnostics. Production runners with a
                # real audit_writer write the original detail to phi_scrub_audit
                # locally; the manifest path is for central's persistence
                # and stays minimal.
            }
            for s in batch.series
        ],
    }


def _outcome_for(s) -> str:
    """Map :class:`SeriesPreviewResult.preview_status` to the
    ``phi_scrub_audit.outcome`` enum the central pydantic model expects.

    Mirrors ``preview_pipeline._record_series`` outcome assignment so a
    re-derive from preview_status alone is correct.
    """
    if s.preview_status == "generated":
        if s.phi_scrub_method == "afni_refacer_v0_7":
            return "success"
        return "not_required"
    if s.preview_status == "quarantined":
        if s.phi_scrub_method == "deface_failed_input":
            return "quarantine_input"
        return "quarantine_runtime"
    if s.preview_status == "skipped":
        if s.phi_scrub_method == "modality_no_deface_needed":
            return "not_required"
        return "skipped"
    return "not_required"


def merge_preview_into_manifest(
    job_result: JobResult,
    *,
    preview_results_by_study: dict[str, dict[str, Any]],
) -> JobResult:
    """jpg-preview-defacing FR-PREVIEW-1.

    The transfer consumer produces a :class:`JobResult` whose ``manifest``
    is a list of per-study dicts. After ``preview_pipeline.process_study``
    runs for each study, the caller passes the resulting per-study
    summary dicts here keyed by ``pseudo_study_uid`` and we merge them
    into ``manifest_entry["preview"]``. This keeps the central-side
    ``complete`` RPC schema additive (FR-PREVIEW-1).

    Returns a NEW :class:`JobResult` — the original is not mutated so
    callers that hold the old reference (e.g. for retry) keep their
    pristine copy.
    """
    new_manifest: list[dict[str, Any]] = []
    for entry in job_result.manifest:
        if not isinstance(entry, dict):
            new_manifest.append(entry)
            continue
        uid = entry.get("pseudo_study_uid")
        if uid and uid in preview_results_by_study:
            merged = dict(entry)
            merged["preview"] = preview_results_by_study[uid]
            new_manifest.append(merged)
        else:
            new_manifest.append(entry)
    return JobResult(
        ok=job_result.ok,
        manifest=new_manifest,
        reason_code=job_result.reason_code,
        reason_detail=job_result.reason_detail,
        retryable=job_result.retryable,
    )
