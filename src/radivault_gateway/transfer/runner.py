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
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

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
