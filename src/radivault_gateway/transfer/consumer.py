"""Gateway transfer consumer daemon (dev-spec §14 G-1).

A minimal loop that claims → processes → completes one transfer_job at a
time. The PACS fetch + De-ID + upload steps are expected to be plugged
in by the existing Flow A pipeline; this module provides the
orchestration shell + long-poll + lease management.

v0.1 keeps the logic **synchronous** so it mirrors the rest of the gateway
package (asyncio integration arrives in v0.1.1 once Flow A migrates).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from radivault_gateway.transfer.claim import Claim, ClaimClient
from radivault_gateway.transfer.config import TransferConfig
from radivault_gateway.transfer.progress import ProgressReporter

log = logging.getLogger("radivault_gateway.transfer.consumer")


@dataclass
class JobResult:
    ok: bool
    manifest: list[dict]
    reason_code: str | None = None
    reason_detail: str | None = None
    retryable: bool = True


class TransferConsumer:
    """Pull-one-run-one loop — run_once is fully unit-testable."""

    def __init__(
        self,
        *,
        config: TransferConfig,
        client: ClaimClient,
        runner: Callable[[Claim, ProgressReporter], JobResult],
        idempotency_key_fn: Callable[[str, str], str] | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._runner = runner
        self._idem = idempotency_key_fn or (lambda tj, kind: f"{tj}:{kind}:{int(time.time())}")

    def run_once(self) -> dict[str, Any]:
        """Claim (at most) one job, run it, report the outcome.

        Returns a dict summary suitable for tests and the CLI ``status`` view.
        """
        if not self._config.enabled:
            return {"action": "disabled"}
        claim = self._client.claim(wait_seconds=self._config.poll_wait_seconds)
        if claim is None:
            return {"action": "empty_queue"}

        reporter = ProgressReporter(interval_seconds=self._config.progress_report_interval_seconds)
        try:
            result = self._runner(claim, reporter)
        except Exception as exc:  # runner itself crashed
            log.exception("transfer_runner_crashed")
            self._client.fail(
                transfer_job_id=claim.transfer_job_id,
                reason_code="OTHER",
                details=str(exc)[:2000],
                retryable=True,
                idempotency_key=self._idem(claim.transfer_job_id, "fail"),
            )
            return {"action": "fail", "transfer_job_id": claim.transfer_job_id}

        if not result.ok:
            self._client.fail(
                transfer_job_id=claim.transfer_job_id,
                reason_code=result.reason_code or "OTHER",
                details=result.reason_detail or "",
                retryable=result.retryable,
                idempotency_key=self._idem(claim.transfer_job_id, "fail"),
            )
            return {"action": "fail", "transfer_job_id": claim.transfer_job_id}

        self._client.complete(
            transfer_job_id=claim.transfer_job_id,
            manifest=result.manifest,
            audit_ref=None,
            idempotency_key=self._idem(claim.transfer_job_id, "complete"),
        )
        return {
            "action": "complete",
            "transfer_job_id": claim.transfer_job_id,
            "n_studies": len(result.manifest),
        }

    def run_forever(self, *, sleep_fn: Callable[[float], None] = time.sleep) -> None:
        """Long-lived loop used by the CLI."""
        if not self._config.enabled:
            log.warning("transfer.enabled=false — consumer exiting")
            return
        backoff = self._config.retry_backoff_initial_seconds
        while True:
            try:
                outcome = self.run_once()
                if outcome["action"] == "empty_queue":
                    sleep_fn(1)
                elif outcome["action"] in ("complete", "fail"):
                    backoff = self._config.retry_backoff_initial_seconds
                elif outcome["action"] == "disabled":
                    return
            except Exception:
                log.exception("transfer_loop_error")
                sleep_fn(min(backoff, self._config.retry_backoff_cap_seconds))
                backoff = min(
                    backoff * self._config.retry_backoff_factor,
                    self._config.retry_backoff_cap_seconds,
                )
