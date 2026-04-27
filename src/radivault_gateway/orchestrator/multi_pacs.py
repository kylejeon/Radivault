"""Multi-PACS sequential sync orchestration (FR-MPS-2).

Iterates over enabled PACS endpoints in priority order, building a
per-endpoint :class:`~radivault_gateway.orchestrator.pipeline.Pipeline`
that shares the gateway-scoped state DB / staging / de-id engine but uses
per-endpoint PACS + upload clients.

Isolation contract (FR-MPS-2 + AC-MPS-4):

- One endpoint's :class:`~radivault_gateway.pacs.PacsError` /
  :class:`~radivault_gateway.upload.UploadError` /
  :class:`Exception` does not abort the loop. Each endpoint emits its own
  ``pacs.run.started`` / ``pacs.run.completed`` / ``pacs.run.failed`` audit
  records — visible in the chain via the ``pacs_id`` meta tag.
- The aggregate :class:`MultiPacsRunSummary` reports per-endpoint
  outcomes; CLI maps it to exit code 0 (all ok) / 2 (any failed).

D-13 scope is sequential. Concurrent / per-endpoint scheduling is
deferred to v0.2 per dev-spec §3.2 + K-MPS-7.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date

from radivault_gateway.audit import AuditLogger
from radivault_gateway.config import GatewayConfig, PacsEndpointConfig
from radivault_gateway.deid import DeidEngine
from radivault_gateway.deid.pixel import PixelDeidEngine
from radivault_gateway.orchestrator.pipeline import Pipeline, RunSummary
from radivault_gateway.pacs import DicomWebPacsClient
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB
from radivault_gateway.upload import UploadClient

log = logging.getLogger("radivault.multi_pacs")


@dataclass
class PacsRunResult:
    """Outcome for a single PACS endpoint inside a multi-PACS sync run."""

    pacs_id: str
    hospital_id: str
    ok: bool
    summary: RunSummary | None = None
    error: str | None = None
    run_id: str = ""


@dataclass
class MultiPacsRunSummary:
    """Aggregate of all per-endpoint outcomes (FR-MPS-2)."""

    runs: list[PacsRunResult] = field(default_factory=list)

    @property
    def successes(self) -> int:
        return sum(1 for r in self.runs if r.ok)

    @property
    def failures(self) -> int:
        return sum(1 for r in self.runs if not r.ok)

    def exit_code(self) -> int:
        """Map to CLI exit code (FR-MPS-2 / FR-MPS-5).

        - 0: every enabled PACS endpoint completed without an exception
          inside the orchestrator. Per-study failures inside a single
          endpoint are reflected in the underlying ``RunSummary.failed``
          counter and surface via ``has_per_study_failures()`` for callers
          that want a finer-grained gate.
        - 2: at least one endpoint raised (network down, auth fail, etc.).
        """
        if self.failures > 0:
            return 2
        return 0

    def has_per_study_failures(self) -> bool:
        """Any per-study failure inside a successful endpoint run."""
        return any(
            r.ok and r.summary is not None and r.summary.failed > 0
            for r in self.runs
        )


def build_pacs_client(
    endpoint: PacsEndpointConfig,
) -> DicomWebPacsClient:
    """Build a :class:`DicomWebPacsClient` from one endpoint config.

    Mirrors the construction in :func:`radivault_gateway.cli.main._build_pipeline`
    so the wire-level behaviour stays identical between single-PACS and
    multi-PACS modes.
    """
    return DicomWebPacsClient(
        endpoint.base_url,
        auth_type=endpoint.auth.type,
        token=endpoint.auth.token,
        username=endpoint.auth.username,
        password=endpoint.auth.password,
        ca_bundle=endpoint.ca_bundle,
    )


def build_upload_client(
    cfg: GatewayConfig,
    *,
    hospital_id: str,
) -> UploadClient:
    """Build a :class:`UploadClient` with the per-hospital bearer token.

    Resolution honours :meth:`CentralConfig.token_for_hospital` —
    map-first, legacy fallback (FR-MPS-6 / K-MPS-6).
    """
    token = cfg.central.token_for_hospital(hospital_id)
    return UploadClient(
        cfg.central.base_url,
        upload_token=token,
        timeout_seconds=cfg.central.upload_timeout_seconds,
        max_retries=cfg.central.max_upload_retries,
        allow_insecure=cfg.central.allow_insecure,
    )


def run_multi_pacs_once(
    cfg: GatewayConfig,
    *,
    state_db: StateDB,
    audit_logger: AuditLogger,
    staging: StagingManager,
    deid: DeidEngine,
    pixel: PixelDeidEngine | None = None,
    pacs_filter: str | None = None,
    since: date | None = None,
    until: date | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    metadata_only: bool = False,
) -> MultiPacsRunSummary:
    """Run one synchronisation cycle across every enabled PACS endpoint.

    Parameters
    ----------
    cfg
        Validated :class:`GatewayConfig` carrying the (possibly multi-)
        PACS list.
    pacs_filter
        Optional endpoint id (FR-MPS-5). When supplied only that endpoint
        runs; other endpoints are skipped (no audit events emitted for
        them) so debugging a single PACS does not pollute the chain.

    Returns
    -------
    MultiPacsRunSummary
        One :class:`PacsRunResult` per attempted endpoint, in execution
        order (priority asc).
    """
    summary = MultiPacsRunSummary()
    endpoints = cfg.enabled_endpoints()
    if pacs_filter is not None:
        endpoints = [e for e in endpoints if e.id == pacs_filter]
        if not endpoints:
            raise ValueError(
                f"--pacs '{pacs_filter}' did not match any enabled endpoint; "
                f"known: {[e.id for e in cfg.pacs_endpoints]}"
            )

    for endpoint in endpoints:
        hospital_id = cfg.hospital_id_for(endpoint)
        run_id = uuid.uuid4().hex
        # Build per-endpoint clients. Each loop iteration owns the
        # http-client lifecycle; the PACS client uses lightweight httpx
        # so reconstructing per-endpoint stays cheap.
        try:
            pacs = build_pacs_client(endpoint)
            upload = build_upload_client(cfg, hospital_id=hospital_id)
        except KeyError as exc:
            # token_for_hospital() may raise when neither the map nor the
            # legacy fallback supplies a token. Surface as a per-endpoint
            # failure instead of aborting the whole run.
            audit_logger.append(
                "pacs.run.failed",
                meta={
                    "pacs_id": endpoint.id,
                    "hospital_id": hospital_id,
                    "run_id": run_id,
                    "error": str(exc),
                    "stage": "client_build",
                },
            )
            log.error(
                "pacs_run_failed",
                extra={
                    "event": "pacs.run.failed",
                    "pacs_id": endpoint.id,
                    "hospital_id": hospital_id,
                    "error": str(exc),
                    "stage": "client_build",
                },
            )
            summary.runs.append(
                PacsRunResult(
                    pacs_id=endpoint.id,
                    hospital_id=hospital_id,
                    ok=False,
                    error=str(exc),
                    run_id=run_id,
                )
            )
            continue

        # FR-MPS-9 — tag subsequent uid_map writes with the source
        # endpoint id. The try/finally below clears the context regardless
        # of pipeline outcome so a stale endpoint label cannot leak into a
        # later legacy DeidEngine call.
        deid.set_pacs_context(endpoint.id)

        # Pipeline carries pacs_id / hospital_id so every audit event
        # auto-tags via Pipeline._emit_audit (FR-MPS-3).
        pipeline = Pipeline(
            cfg,
            state_db=state_db,
            audit_logger=audit_logger,
            staging=staging,
            deid=deid,
            pacs=pacs,
            upload=upload,
            pixel=pixel,
            pacs_id=endpoint.id,
            hospital_id=hospital_id,
        )

        # Per-endpoint run start / completed / failed audit envelope.
        # We append directly via audit_logger here (rather than via the
        # Pipeline's _emit_audit) so the run-level events have an explicit
        # ``run_id`` and ``stage`` field set; the Pipeline-internal events
        # still get pacs_id via the per-call setdefault.
        audit_logger.append(
            "pacs.run.started",
            meta={
                "pacs_id": endpoint.id,
                "hospital_id": hospital_id,
                "run_id": run_id,
                "base_url": endpoint.base_url,
            },
        )
        run_summary = None
        run_exc: Exception | None = None
        try:
            run_summary = pipeline.run_once(
                since=since,
                until=until,
                dry_run=dry_run,
                limit=limit,
                metadata_only=metadata_only,
            )
        except Exception as exc:  # noqa: BLE001 — orchestrator-level isolation
            run_exc = exc

        if run_exc is not None:
            exc = run_exc
            # Per FR-MPS-2 / AC-MPS-4 a single PACS exception (network
            # down, auth fail, sidecar unreachable, …) must NOT abort the
            # remaining endpoints. We log + record + continue. The audit
            # log keeps the partial events the pipeline already emitted.
            audit_logger.append(
                "pacs.run.failed",
                meta={
                    "pacs_id": endpoint.id,
                    "hospital_id": hospital_id,
                    "run_id": run_id,
                    "error": str(exc)[:500],
                    "error_type": type(exc).__name__,
                },
            )
            log.error(
                "pacs_run_failed",
                extra={
                    "event": "pacs.run.failed",
                    "pacs_id": endpoint.id,
                    "hospital_id": hospital_id,
                    "error": str(exc)[:500],
                    "error_type": type(exc).__name__,
                },
            )
            summary.runs.append(
                PacsRunResult(
                    pacs_id=endpoint.id,
                    hospital_id=hospital_id,
                    ok=False,
                    error=str(exc)[:500],
                    run_id=run_id,
                )
            )
            # Best-effort cleanup of the per-endpoint http clients — both
            # are httpx-backed so calling close() is the right idiom.
            try:
                upload.close()
            except Exception:  # noqa: BLE001
                pass
            continue

        audit_logger.append(
            "pacs.run.completed",
            meta={
                "pacs_id": endpoint.id,
                "hospital_id": hospital_id,
                "run_id": run_id,
                "uploaded": run_summary.uploaded,
                "skipped": run_summary.skipped,
                "quarantined": run_summary.quarantined,
                "failed": run_summary.failed,
                "total": run_summary.total,
            },
        )
        log.info(
            "pacs_run_completed",
            extra={
                "event": "pacs.run.completed",
                "pacs_id": endpoint.id,
                "hospital_id": hospital_id,
                "uploaded": run_summary.uploaded,
                "skipped": run_summary.skipped,
                "failed": run_summary.failed,
            },
        )
        summary.runs.append(
            PacsRunResult(
                pacs_id=endpoint.id,
                hospital_id=hospital_id,
                ok=True,
                summary=run_summary,
                run_id=run_id,
            )
        )
        try:
            upload.close()
        except Exception:  # noqa: BLE001
            pass

    # Clear the deid pacs_id context so a subsequent legacy call into
    # ``deid.pseudo_uid`` (e.g. from de-id-test CLI) does not pick up a
    # stale endpoint label.
    deid.set_pacs_context(None)
    return summary
