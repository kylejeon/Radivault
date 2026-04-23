"""Adapter that turns a transfer-job claim into PACS fetch + De-ID + upload.

v0.1 keeps the real PACS/De-ID/upload wiring pluggable so the gateway
package doesn't grow coupling with the fulfilment subsystem. The CLI
wires the default ``mock_runner`` (for ``transfer test`` smoke runs);
production deployments swap in the real pipeline.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from radivault_gateway.transfer.claim import Claim
from radivault_gateway.transfer.consumer import JobResult
from radivault_gateway.transfer.progress import ProgressReporter


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
