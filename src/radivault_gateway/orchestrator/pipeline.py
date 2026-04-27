"""Pipeline coordinator — PACS → De-ID → Staging → Upload → Audit.

Implements the flow described in dev-spec §8.1. Single-threaded per-study for
v0.1; the scheduler calls :meth:`Pipeline.run_once` at each poll tick.

Failure modes mirror §8.2: fetch failures → state=failed_fetch with retry
bookkeeping; de-id quarantine → state=quarantined with audit record; upload
failures are surfaced as :class:`UploadError` and the orchestrator records
``failed_upload`` in the state DB.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from typing import Any

from radivault_gateway.audit import AuditLogger
from radivault_gateway.config import GatewayConfig
from radivault_gateway.deid import DeidEngine, QuarantineRequired
from radivault_gateway.deid.method_codes import resolve_flow_a_method_codes
from radivault_gateway.deid.pixel import (
    PixelDeidEngine,
    PixelDeidResult,
    PixelQuarantineRequired,
)
from radivault_gateway.pacs import DicomWebPacsClient, PacsError, StudySummary
from radivault_gateway.preview_pipeline import (
    SeriesInput,
    is_pipeline_enabled as is_preview_pipeline_enabled,
    process_study as run_preview_process_study,
)
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB, StudyState
from radivault_gateway.upload import UploadClient, UploadError

log = logging.getLogger("radivault.pipeline")


@dataclass
class StudyOutcome:
    original_study_uid: str
    pseudo_study_uid: str | None
    state: StudyState
    reason: str | None = None
    duration_ms: int = 0
    fetch_ms: int = 0
    deid_ms: int = 0
    upload_ms: int = 0


@dataclass
class RunSummary:
    uploaded: int = 0
    quarantined: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0
    # v0.2 de-id-pixel counters (surfaced in status output).
    pixel_deided: int = 0
    pixel_failed: int = 0
    outcomes: list[StudyOutcome] = field(default_factory=list)


class Pipeline:
    def __init__(
        self,
        config: GatewayConfig,
        *,
        state_db: StateDB,
        audit_logger: AuditLogger,
        staging: StagingManager,
        deid: DeidEngine,
        pacs: DicomWebPacsClient,
        upload: UploadClient,
        pixel: PixelDeidEngine | None = None,
        pacs_id: str | None = None,
        hospital_id: str | None = None,
    ) -> None:
        self._cfg = config
        self._db = state_db
        self._audit = audit_logger
        self._staging = staging
        self._deid = deid
        self._pacs = pacs
        self._upload = upload
        # v0.2 de-id-pixel: opt-in, None when cfg.deid.pixel.enabled=false.
        self._pixel = pixel
        # FR-MPS-3 audit pacs_id meta: when constructed for a specific
        # endpoint these tags every audit event. ``None`` means the legacy
        # single-PACS Pipeline (backward compat — events still emit, just
        # without the pacs_id field — so existing audit logs continue to
        # parse and verify_chain stays PASS).
        self._pacs_id = pacs_id
        self._hospital_id = hospital_id

    def _emit_audit(
        self,
        event: str,
        *,
        target: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        ts: str | None = None,
    ) -> Any:
        """Append an audit event, injecting ``pacs_id`` / ``hospital_id`` meta.

        FR-MPS-3 / K-MPS-4 — single unified chain with pacs_id meta on every
        PACS-scoped event. Resolution order:

        - ``meta`` already supplies ``pacs_id`` → preserved (caller wins).
        - else ``self._pacs_id`` is set → injected.
        - else (legacy single-PACS Pipeline constructed without pacs_id)
          → no pacs_id field is added, preserving the existing wire shape.

        Same logic for ``hospital_id``. The chain hash naturally covers the
        meta dict's canonical JSON, so verify.py PASS is preserved as long
        as the writer and reader agree on the dict contents at flush time.
        """
        merged = dict(meta or {})
        if self._pacs_id is not None:
            merged.setdefault("pacs_id", self._pacs_id)
        if self._hospital_id is not None:
            merged.setdefault("hospital_id", self._hospital_id)
        return self._audit.append(event, target=target, meta=merged, ts=ts)

    def run_once(
        self,
        *,
        since: date | None = None,
        until: date | None = None,
        dry_run: bool = False,
        limit: int | None = None,
        metadata_only: bool = False,
    ) -> RunSummary:
        """Perform one full sync cycle. Returns a summary with per-study outcomes.

        When ``metadata_only`` is True the pipeline switches to the
        gateway-flow-a-qido fast-path: it pulls a single QIDO-RS row per
        study, synthesises the Flow A manifest from its counters, and POSTs
        only the manifest to Central. No WADO metadata fetch, no de-id, no
        disk I/O, no staging directory — typical per-study latency drops from
        ~14 s to ~0.3 s on Orthanc. Pixel-level de-ID and burn-in handling
        are deferred to Flow B (ARCHITECTURE.md §4), which is invoked at
        order-fulfillment time.
        """
        summary = RunSummary()

        if self._staging.backpressure_triggered():
            log.warning(
                "staging backpressure active; skipping fetch",
                extra={"usage_pct": round(self._staging.disk_usage_pct(), 1)},
            )
            self._emit_audit(
                "staging.backpressure",
                meta={"usage_pct": round(self._staging.disk_usage_pct(), 1)},
            )
            return summary

        today = date.today()
        if until is None:
            until = today
        if since is None:
            since = today - timedelta(days=self._cfg.pacs.query.lookback_days)

        self._emit_audit(
            "pacs.query",
            meta={
                "since": since.isoformat(),
                "until": until.isoformat(),
                "modalities": self._cfg.pacs.query.modalities,
            },
        )
        try:
            studies = self._pacs.query_studies(
                since, until, modalities=self._cfg.pacs.query.modalities
            )
        except PacsError as exc:
            self._emit_audit(
                "pacs.query.failed",
                meta={"error": str(exc), "status_code": exc.status_code},
            )
            log.error("pacs query failed", extra={"error": str(exc)})
            summary.failed += 1
            return summary
        if limit is not None:
            studies = studies[:limit]
        summary.total = len(studies)
        log.info("pacs query ok", extra={"returned": summary.total})

        for study in studies:
            outcome = self._process_study(
                study, dry_run=dry_run, metadata_only=metadata_only
            )
            summary.outcomes.append(outcome)
            if outcome.state == StudyState.UPLOADED and outcome.reason == "already_uploaded":
                # gateway-sync-skip-uploaded: already ingested, short-circuited
                # without touching PACS/de-id. Keep out of the uploaded counter
                # so ``skipped`` accurately reflects no-op cycles.
                summary.skipped += 1
            elif outcome.state == StudyState.UPLOADED:
                summary.uploaded += 1
            elif outcome.state == StudyState.QUARANTINED:
                summary.quarantined += 1
            elif outcome.state == StudyState.PIXEL_FAILED:
                summary.pixel_failed += 1
                summary.quarantined += 1
            elif outcome.state == StudyState.PIXEL_DEIDED:
                summary.pixel_deided += 1
                summary.uploaded += 1
            elif outcome.state in {
                StudyState.FAILED_FETCH,
                StudyState.FAILED_DEID,
                StudyState.FAILED_REVERIFY,
                StudyState.FAILED_UPLOAD,
            }:
                summary.failed += 1
            else:
                summary.skipped += 1
        return summary

    # ---- study-level orchestration ----

    def _process_study(
        self, study: StudySummary, *, dry_run: bool, metadata_only: bool = False
    ) -> StudyOutcome:
        started = datetime.now()
        original_uid = study.study_instance_uid

        # Gateway-side short-circuit (gateway-sync-skip-uploaded). Central's
        # idempotency middleware already replays duplicate ingests correctly,
        # but re-fetching and re-de-identifying an already-uploaded study
        # wastes PACS bandwidth and CPU — noticeable during demo re-seeds and
        # rehearsals. Skip before touching the filesystem so no tmp dirs are
        # created. Applies equally to metadata-only (Flow A) and full-payload
        # (Flow B) because both transitions write ``original_study_uid_hash``
        # on the UPLOADED mark_state.
        if self._db.is_study_uploaded(original_uid):
            self._emit_audit(
                "sync.skipped",
                target={"original_study_uid_hash": _short_hash(original_uid)},
                meta={"reason": "already_uploaded"},
            )
            return StudyOutcome(
                original_study_uid=original_uid,
                pseudo_study_uid=None,
                state=StudyState.UPLOADED,
                reason="already_uploaded",
                duration_ms=_elapsed_ms(started),
            )

        # Flow A fast-path (gateway-flow-a-qido): a single QIDO-RS row is
        # enough to build the manifest — no WADO metadata pull, no de-id,
        # no staging I/O. Flow B (below) continues to do the full pipeline.
        if metadata_only:
            return self._process_study_metadata_only(
                study, original_uid=original_uid, started=started, dry_run=dry_run
            )

        pseudo_uid: str | None = None
        fetch_dir: Path | None = None

        try:
            fetch_dir = Path(tempfile.mkdtemp(prefix="radivault_fetch_"))
            fetch_started = datetime.now()
            try:
                # Flow B (full-payload): standard multipart WADO-RS
                # ``/studies/{uid}`` transferring every frame. The Flow A
                # fast-path short-circuited above.
                fetch = self._pacs.fetch_study(original_uid, fetch_dir)
            except PacsError as exc:
                self._emit_audit(
                    "pacs.fetch.failed",
                    meta={"error": str(exc), "status_code": exc.status_code},
                    target={"original_study_uid_hash": _short_hash(original_uid)},
                )
                return StudyOutcome(
                    original_study_uid=original_uid,
                    pseudo_study_uid=None,
                    state=StudyState.FAILED_FETCH,
                    reason=str(exc),
                    duration_ms=_elapsed_ms(started),
                )
            fetch_ms = _elapsed_ms(fetch_started)
            self._emit_audit(
                "pacs.fetch.completed",
                target={"original_study_uid_hash": _short_hash(original_uid)},
                meta={
                    "n_instances": len(fetch.instance_paths),
                    "bytes": fetch.bytes_total,
                    "duration_ms": fetch_ms,
                },
            )

            # De-ID
            staging_dir = Path(tempfile.mkdtemp(prefix="radivault_deid_"))
            self._emit_audit(
                "deid.started",
                target={"original_study_uid_hash": _short_hash(original_uid)},
                meta={"n_instances": len(fetch.instance_paths)},
            )
            deid_started = datetime.now()
            try:
                deid_result = self._deid.deidentify_study(fetch_dir, staging_dir)
            except QuarantineRequired as exc:
                pseudo_uid = None
                qid = f"quarantine_{_short_hash(original_uid)}"
                # FR-11 / AC-8: preserve the offending artifacts in the
                # quarantine directory rather than deleting them. We move
                # the original fetch_dir contents (pre-deid) so a DPO review
                # can inspect the exact evidence. The partial de-id staging_dir
                # (if any) is discarded because it was never a completed de-id.
                quarantine_path = self._staging.move_to_quarantine(fetch_dir, qid)
                self._db.upsert_study_job(
                    qid,
                    state=StudyState.QUARANTINED,
                    modalities=study.modalities_in_study,
                )
                self._db.add_quarantine(
                    qid,
                    reason=f"burned_in_annotation:{exc.reason}",
                    payload_path=str(quarantine_path),
                )
                self._emit_audit(
                    "quarantine.flagged",
                    meta={
                        "reason": exc.reason,
                        "n_files": len(exc.offending_sops),
                        "quarantine_path": str(quarantine_path),
                    },
                )
                log.warning(
                    "quarantine",
                    extra={"reason": exc.reason, "quarantine_path": str(quarantine_path)},
                )
                shutil.rmtree(staging_dir, ignore_errors=True)
                # fetch_dir was consumed by move_to_quarantine; prevent the
                # finally-block rmtree from touching it.
                fetch_dir = None
                return StudyOutcome(
                    original_study_uid=original_uid,
                    pseudo_study_uid=None,
                    state=StudyState.QUARANTINED,
                    reason=exc.reason,
                    duration_ms=_elapsed_ms(started),
                    fetch_ms=fetch_ms,
                )
            except Exception as exc:
                self._emit_audit(
                    "deid.failed",
                    meta={"error": str(exc)},
                )
                log.exception("deid failed")
                shutil.rmtree(staging_dir, ignore_errors=True)
                return StudyOutcome(
                    original_study_uid=original_uid,
                    pseudo_study_uid=None,
                    state=StudyState.FAILED_DEID,
                    reason=str(exc),
                    duration_ms=_elapsed_ms(started),
                    fetch_ms=fetch_ms,
                )
            deid_ms = _elapsed_ms(deid_started)
            pseudo_uid = deid_result.pseudo_study_uid
            self._emit_audit(
                "deid.completed",
                target={"pseudo_study_uid": pseudo_uid},
                meta={
                    "n_instances": deid_result.n_instances,
                    "ruleset_version": self._cfg.deid.ruleset_version,
                    "salt_version": self._cfg.deid.salt_version,
                    "duration_ms": deid_ms,
                },
            )

            # FR-13 reverify
            reverify = self._deid.reverify(staging_dir)
            if not reverify.ok:
                # Per dev-spec §8.2 move the partially de-id'd artifacts into
                # the quarantine directory (not staging) so operators can review
                # what slipped past the Annex E rules without deleting evidence.
                quarantine_path = self._staging.move_to_quarantine(staging_dir, pseudo_uid)
                self._emit_audit(
                    "deid.reverify_failed",
                    target={"pseudo_study_uid": pseudo_uid},
                    meta={
                        "n_offending": len(reverify.offending),
                        "quarantine_path": str(quarantine_path),
                    },
                )
                self._db.upsert_study_job(
                    pseudo_uid,
                    state=StudyState.FAILED_REVERIFY,
                    modalities=study.modalities_in_study,
                    n_instances=deid_result.n_instances,
                    n_bytes=deid_result.n_bytes,
                )
                self._db.add_quarantine(
                    pseudo_uid,
                    reason="reverify_failed",
                    payload_path=str(quarantine_path),
                )
                return StudyOutcome(
                    original_study_uid=original_uid,
                    pseudo_study_uid=pseudo_uid,
                    state=StudyState.FAILED_REVERIFY,
                    reason="reverify_failed",
                    duration_ms=_elapsed_ms(started),
                    fetch_ms=fetch_ms,
                    deid_ms=deid_ms,
                )

            # v0.2 de-id-pixel: opt-in pixel stage (FR-31). Skipped entirely
            # when ``self._pixel is None`` (cfg.deid.pixel.enabled=false) so
            # the downstream behaviour remains bit-equivalent to v0.1.
            if self._pixel is not None:
                pixel_outcome = self._run_pixel_stage(
                    pseudo_uid=pseudo_uid,
                    staging_dir=staging_dir,
                    study=study,
                    started=started,
                    fetch_ms=fetch_ms,
                    deid_ms=deid_ms,
                    original_uid=original_uid,
                )
                if pixel_outcome is not None:
                    # Pixel stage routed to quarantine; fetch_dir already
                    # cleaned by helper. Short-circuit to the outcome.
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    fetch_dir = None
                    return pixel_outcome

            # FR-14 canonical layout: preserve the series-nested tree the
            # de-id engine produced under ``{staging_root}/{pseudo_study_uid}/
            # {pseudo_series_uid}/{pseudo_sop_uid}.dcm``.
            final_staging = self._staging.ensure_study_dir(pseudo_uid)
            for path in deid_result.output_paths:
                series_name = path.parent.name
                target_dir = final_staging / series_name
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / path.name
                shutil.move(str(path), str(target))
            shutil.rmtree(staging_dir, ignore_errors=True)
            staged_files = sorted(final_staging.rglob("*.dcm"))
            self._emit_audit(
                "staging.written",
                target={"pseudo_study_uid": pseudo_uid},
                meta={"n_files": len(staged_files)},
            )
            self._db.upsert_study_job(
                pseudo_uid,
                state=StudyState.DEIDED,
                modalities=study.modalities_in_study,
                n_instances=deid_result.n_instances,
                n_bytes=deid_result.n_bytes,
            )
            self._db.mark_state(pseudo_uid, StudyState.DEIDED)

            if dry_run:
                self._emit_audit(
                    "upload.skipped",
                    target={"pseudo_study_uid": pseudo_uid},
                    meta={"reason": "dry_run"},
                )
                return StudyOutcome(
                    original_study_uid=original_uid,
                    pseudo_study_uid=pseudo_uid,
                    state=StudyState.DEIDED,
                    reason="dry_run",
                    duration_ms=_elapsed_ms(started),
                    fetch_ms=fetch_ms,
                    deid_ms=deid_ms,
                )

            # metadata-thumbnail-ingest FR-META-2 + FR-THUMB-1: extract the
            # 12 buyer-facet fields and the middle-slice thumbnail from the
            # de-id'd staged DICOM files BEFORE upload. Failures degrade
            # gracefully — the manifest just falls back to v1 shape.
            try:
                from radivault_gateway.extract import extract_study_metadata
                from radivault_gateway.thumbnail import generate_thumbnail

                study_metadata = extract_study_metadata(staged_files)
                primary_modality = (
                    study.modalities_in_study[0] if study.modalities_in_study else None
                )
                thumb = generate_thumbnail(
                    staged_files,
                    modality=primary_modality,
                    body_part=study_metadata.body_part_examined,
                )
            except Exception as exc:  # noqa: BLE001 — never fail ingest on metadata
                log.warning(
                    "metadata_extract_failed",
                    extra={"event": "metadata.extract.error", "error": str(exc)[:200]},
                )
                study_metadata = None
                thumb = None

            # jpg-preview-defacing FR-PREVIEW-1 / FR-PREVIEW-2 / FR-PREVIEW-3:
            # run the per-series preview pipeline against the just-staged
            # DICOM tree. Sits between staging.written and upload.started so
            # the per-series ``preview_status`` / ``preview_frame_count``
            # land in the manifest the same RPC carries (central's ingest
            # router persists them via ``_persist_preview_batch``).
            #
            # FR-DEFACE-9 invariant: a preview failure NEVER aborts ingest.
            # The whole block is wrapped so any boto3 / DB / sidecar error
            # is logged + swallowed; the manifest just ships without a
            # ``preview`` key (legacy backward-compat). FR-NEWONLY-2: this
            # touches only the in-flight study — no backfill of existing
            # rows.
            preview_block: dict[str, Any] | None = None
            if is_preview_pipeline_enabled() and study_metadata is not None:
                try:
                    preview_block = self._run_preview_pipeline(
                        pseudo_study_uid=pseudo_uid,
                        final_staging=final_staging,
                        study_metadata=study_metadata,
                    )
                except Exception as exc:  # noqa: BLE001 — preview never blocks ingest
                    log.warning(
                        "preview_pipeline_swallowed",
                        extra={
                            "event": "preview.pipeline.error",
                            "pseudo_study_uid": pseudo_uid,
                            "error": str(exc)[:200],
                        },
                    )
                    self._emit_audit(
                        "preview.failed",
                        target={"pseudo_study_uid": pseudo_uid},
                        meta={"error": str(exc)[:200]},
                    )

            # Upload
            manifest = self._upload.build_manifest(
                gateway_id=self._cfg.agent.gateway_id,
                hospital_id=self._cfg.agent.hospital_id,
                pseudo_study_uid=pseudo_uid,
                modalities=study.modalities_in_study,
                ruleset_version=self._cfg.deid.ruleset_version,
                salt_version=self._cfg.deid.salt_version,
                method_codes=_method_codes(self._cfg),
                dcm_files=staged_files,
                study_metadata=study_metadata,
                thumbnail=thumb,
            )
            # Manifest is a plain dict — central's ``Manifest`` pydantic
            # model has ``extra="allow"`` so the additive ``preview`` key
            # passes validation and is read by ``_persist_preview_batch``.
            if preview_block is not None:
                manifest["preview"] = preview_block
            self._emit_audit(
                "upload.started",
                target={"pseudo_study_uid": pseudo_uid},
                meta={"n_files": len(staged_files), "bytes": manifest["total_bytes"]},
            )
            self._db.mark_state(pseudo_uid, StudyState.UPLOADING)
            upload_started = datetime.now()
            try:
                result = self._upload.upload_study(manifest, staged_files)
            except UploadError as exc:
                self._emit_audit(
                    "upload.failed",
                    target={"pseudo_study_uid": pseudo_uid},
                    meta={"error": str(exc), "status_code": exc.status_code},
                )
                self._db.mark_state(pseudo_uid, StudyState.FAILED_UPLOAD, last_error=str(exc))
                self._db.schedule_retry(
                    pseudo_uid,
                    (datetime.now(tz=UTC) + timedelta(minutes=5)).isoformat(),
                )
                return StudyOutcome(
                    original_study_uid=original_uid,
                    pseudo_study_uid=pseudo_uid,
                    state=StudyState.FAILED_UPLOAD,
                    reason=str(exc),
                    duration_ms=_elapsed_ms(started),
                    fetch_ms=fetch_ms,
                    deid_ms=deid_ms,
                )
            upload_ms = _elapsed_ms(upload_started)
            self._emit_audit(
                "upload.completed",
                target={"pseudo_study_uid": pseudo_uid},
                meta={
                    "central_job_id": result.job_id,
                    "bytes": manifest["total_bytes"],
                    "duration_ms": upload_ms,
                },
            )
            self._db.upsert_study_job(
                pseudo_uid,
                state=StudyState.UPLOADED,
                modalities=study.modalities_in_study,
                n_instances=deid_result.n_instances,
                n_bytes=deid_result.n_bytes,
                central_job_id=result.job_id,
            )
            # Persist the original-UID hash alongside the UPLOADED mark so
            # the next sync can short-circuit via ``is_study_uploaded`` —
            # gateway-sync-skip-uploaded. Full-payload (Flow B) path.
            self._db.mark_state(
                pseudo_uid, StudyState.UPLOADED, original_uid=original_uid
            )
            self._db.clear_retry(pseudo_uid)

            # Cleanup staging (FR-15)
            if self._staging.cleanup_study(pseudo_uid):
                self._emit_audit(
                    "staging.cleanup",
                    target={"pseudo_study_uid": pseudo_uid},
                    meta={},
                )
            else:
                self._emit_audit(
                    "staging.cleanup_failed",
                    target={"pseudo_study_uid": pseudo_uid},
                    meta={},
                )

            return StudyOutcome(
                original_study_uid=original_uid,
                pseudo_study_uid=pseudo_uid,
                state=StudyState.UPLOADED,
                duration_ms=_elapsed_ms(started),
                fetch_ms=fetch_ms,
                deid_ms=deid_ms,
                upload_ms=upload_ms,
            )
        finally:
            if fetch_dir is not None:
                shutil.rmtree(fetch_dir, ignore_errors=True)

    # ---- pixel stage (v0.2) ----

    def _run_pixel_stage(
        self,
        *,
        pseudo_uid: str,
        staging_dir: Path,
        study: StudySummary,
        started: datetime,
        fetch_ms: int,
        deid_ms: int,
        original_uid: str,
    ) -> StudyOutcome | None:
        """Run pixel triage + OCR + defacing. Returns a terminal outcome on
        quarantine / failure, or ``None`` when the caller should continue."""
        assert self._pixel is not None
        self._db.mark_state(pseudo_uid, StudyState.PIXEL_PROCESSING)
        pixel_started = datetime.now()
        # Determine study-level inputs from the first staged instance.
        study_description, body_part = _sample_pixel_context(staging_dir)
        modality_set = {str(m).upper() for m in study.modalities_in_study}
        try:
            result: PixelDeidResult = self._pixel.process_study(
                staging_dir,
                pseudo_study_uid=pseudo_uid,
                study_description=study_description,
                modality_set=modality_set,
                body_part=body_part,
            )
        except PixelQuarantineRequired as exc:
            quarantine_path = self._staging.move_to_quarantine(staging_dir, pseudo_uid)
            # AC-14 / FR-37: append to the hash-chained audit.log first so we
            # can cross-reference the pixel_audit_event row via ``audit_seq``
            # (AC-21). ``AuditLogger.append`` returns an ``AuditRecord`` with
            # the assigned seq.
            record = self._emit_audit(
                "pixel.quarantined",
                target={"pseudo_study_uid": pseudo_uid},
                meta={
                    "code": exc.code,
                    "reason": exc.reason,
                    "quarantine_path": str(quarantine_path),
                },
            )
            self._db.add_pixel_audit_event(
                pseudo_study_uid=pseudo_uid,
                op="quarantine",
                outcome="quarantine",
                reason=exc.code,
                audit_seq=record.seq,
            )
            self._db.mark_state(pseudo_uid, StudyState.PIXEL_FAILED, last_error=exc.code)
            self._db.add_quarantine(
                pseudo_uid,
                reason=f"pixel:{exc.code}",
                payload_path=str(quarantine_path),
            )
            log.warning(
                "pixel.quarantined",
                extra={
                    "event": "pixel.quarantined",
                    "pixel": {
                        "stage": "quarantine",
                        "error_code": exc.code,
                        "reason": exc.reason,
                    },
                    "pseudo_study_uid": pseudo_uid,
                },
            )
            return StudyOutcome(
                original_study_uid=study.study_instance_uid,
                pseudo_study_uid=pseudo_uid,
                state=StudyState.PIXEL_FAILED,
                reason=exc.code,
                duration_ms=_elapsed_ms(started),
                fetch_ms=fetch_ms,
                deid_ms=deid_ms,
            )
        except Exception as exc:
            # Engine-internal failure. Per FR-33, escalate to quarantine when
            # quarantine_on_failure=true (default).
            log.exception("pixel engine failed")
            if self._cfg.deid.pixel.quarantine_on_failure:
                quarantine_path = self._staging.move_to_quarantine(staging_dir, pseudo_uid)
                record = self._emit_audit(
                    "pixel.quarantined",
                    target={"pseudo_study_uid": pseudo_uid},
                    meta={
                        "code": "ERR_PIXEL_OCR_ENGINE_FAILURE",
                        "error": str(exc),
                        "quarantine_path": str(quarantine_path),
                    },
                )
                self._db.add_pixel_audit_event(
                    pseudo_study_uid=pseudo_uid,
                    op="quarantine",
                    outcome="failure",
                    reason="ERR_PIXEL_OCR_ENGINE_FAILURE",
                    audit_seq=record.seq,
                )
                self._db.mark_state(
                    pseudo_uid,
                    StudyState.PIXEL_FAILED,
                    last_error="ERR_PIXEL_OCR_ENGINE_FAILURE",
                )
                self._db.add_quarantine(
                    pseudo_uid,
                    reason="pixel:ERR_PIXEL_OCR_ENGINE_FAILURE",
                    payload_path=str(quarantine_path),
                )
                return StudyOutcome(
                    original_study_uid=study.study_instance_uid,
                    pseudo_study_uid=pseudo_uid,
                    state=StudyState.PIXEL_FAILED,
                    reason="ERR_PIXEL_OCR_ENGINE_FAILURE",
                    duration_ms=_elapsed_ms(started),
                    fetch_ms=fetch_ms,
                    deid_ms=deid_ms,
                )
            raise

        pixel_duration_ms = _elapsed_ms(pixel_started)
        completed_record = self._emit_audit(
            "pixel.completed",
            target={"pseudo_study_uid": pseudo_uid},
            meta={
                "decision": result.decision,
                "ocr_applied": result.ocr_applied,
                "defacing_applied": result.defacing_applied,
                "n_boxes_redacted": result.n_boxes_redacted,
                "removed_voxel_ratio": result.removed_voxel_ratio,
                "duration_ms": pixel_duration_ms,
                "library_ocr": result.library_ocr,
                "library_deface": result.library_deface,
                "fallback_used": result.fallback_used,
            },
        )
        self._db.add_pixel_audit_event(
            pseudo_study_uid=pseudo_uid,
            op="triage",
            outcome="success",
            reason=result.decision,
            audit_seq=completed_record.seq,
        )
        if result.ocr_applied:
            self._db.add_pixel_audit_event(
                pseudo_study_uid=pseudo_uid,
                op="ocr",
                outcome="success",
                library=result.library_ocr,
                duration_ms=result.ocr_duration_ms,
                box_count=result.n_boxes_redacted,
                avg_confidence=result.avg_confidence or None,
                min_confidence=result.min_confidence or None,
                max_confidence=result.max_confidence or None,
                audit_seq=completed_record.seq,
            )
        if result.defacing_applied:
            self._db.add_pixel_audit_event(
                pseudo_study_uid=pseudo_uid,
                op="deface",
                outcome="success",
                library=result.library_deface,
                duration_ms=result.deface_duration_ms,
                removed_voxel_ratio=result.removed_voxel_ratio,
                audit_seq=completed_record.seq,
            )
        # AC-14 / FR-37: emit a dedicated hash-chained ``pixel.deface.fallback_used``
        # event whenever the pixel engine escalated from the primary defacing
        # library to the fallback. Previously this information only existed in
        # the WARN app log — which is not tamper-evident and not visible to
        # ``audit verify``.
        if result.fallback_used:
            fallback_record = self._emit_audit(
                "pixel.deface.fallback_used",
                target={"pseudo_study_uid": pseudo_uid},
                meta={
                    "fallback_library": result.library_deface,
                    "primary_error_code": result.fallback_reason,
                },
            )
            self._db.add_pixel_audit_event(
                pseudo_study_uid=pseudo_uid,
                op="deface",
                outcome="fallback",
                library=result.library_deface,
                reason=result.fallback_reason,
                audit_seq=fallback_record.seq,
            )
        log.info(
            "pixel.completed",
            extra={
                "event": "pixel.completed",
                "pixel": {
                    "stage": "verify",
                    "library": result.library_ocr or result.library_deface,
                    "decision": result.decision,
                    "duration_ms": pixel_duration_ms,
                    "redaction_count": result.n_boxes_redacted,
                    "defaced_voxel_ratio": result.removed_voxel_ratio,
                    "confidence_p50": result.avg_confidence,
                    "confidence_p10": result.p10_confidence,
                },
                "pseudo_study_uid": pseudo_uid,
            },
        )
        return None


    # ---- jpg-preview-defacing wiring (FR-PREVIEW-1 / FR-PREVIEW-2) ----

    def _run_preview_pipeline(
        self,
        *,
        pseudo_study_uid: str,
        final_staging: Path,
        study_metadata: Any,
    ) -> dict[str, Any] | None:
        """Run ``preview_pipeline.process_study`` for the current study and
        return a JSON-friendly dict ready for ``manifest['preview']``.

        Design notes
        ------------
        - Series inputs are derived from :class:`StudyMetadata.series` (the
          12-facet extract already walked the staged tree). Each series
          maps to a dir at ``{final_staging}/{pseudo_series_uid}``.
        - We construct :class:`PreviewClients` lazily and dispose of the
          SQLAlchemy engine + boto3 session at the end of this call so a
          failure here cannot leak resources back into the orchestrator.
        - Any exception bubbles up to the caller, which logs+swallows it
          (FR-DEFACE-9). We do **not** swallow inside this helper because
          the caller is the canonical fail-soft boundary and tests can
          assert behaviour by patching this method.
        """
        # Lazy import — preview_clients pulls in boto3 / sqlalchemy. Keeps
        # the pipeline module importable in environments without those
        # extras (e.g. unit tests that don't exercise the preview path).
        from radivault_gateway.preview_clients import PreviewClients

        series_inputs: list[SeriesInput] = []
        series_meta: list[dict] = list(getattr(study_metadata, "series", []) or [])
        for idx, series in enumerate(series_meta, start=1):
            pseudo_series_uid = series.get("pseudo_series_uid")
            if not pseudo_series_uid:
                continue
            series_dir = final_staging / pseudo_series_uid
            if not series_dir.exists() or not series_dir.is_dir():
                # Defensive — extract.py and the on-disk staging layout
                # should agree, but skip silently rather than raise.
                log.debug(
                    "preview_series_dir_missing",
                    extra={
                        "event": "preview.series.miss",
                        "pseudo_series_uid": pseudo_series_uid,
                        "series_dir": str(series_dir),
                    },
                )
                continue
            series_inputs.append(
                SeriesInput(
                    pseudo_series_uid=pseudo_series_uid,
                    series_num=idx,
                    series_dir=series_dir,
                    modality=series.get("modality"),
                    body_part=series.get("body_part"),
                    series_description=series.get("series_description_clean"),
                    protocol_name=None,
                )
            )

        if not series_inputs:
            log.info(
                "preview_pipeline_no_series",
                extra={
                    "event": "preview.pipeline.no_series",
                    "pseudo_study_uid": pseudo_study_uid,
                },
            )
            return None

        study_description = getattr(study_metadata, "study_description", None)

        with PreviewClients.from_env() as clients:
            batch = run_preview_process_study(
                pseudo_study_uid=pseudo_study_uid,
                series_inputs=series_inputs,
                study_description=study_description,
                minio_client=clients.minio,
                audit_writer=clients.audit,
                frame_writer=clients.frames,
            )

        # Convert dataclasses → JSON-friendly dict matching
        # ``radivault_central.manifest.schema.PreviewBatch`` (extra=allow).
        # Reuses the same shape the CLI/runner path emits (transfer/runner.py
        # ``_preview_to_dict``) so central's ``_persist_preview_batch`` sees
        # identical payloads from both code paths.
        from radivault_gateway.transfer.runner import (
            _preview_to_dict as _preview_batch_to_dict,
        )

        preview_dict = _preview_batch_to_dict(batch)
        log.info(
            "preview_pipeline_done",
            extra={
                "event": "preview.completed"
                if not batch.skipped
                else "preview.skipped",
                "pseudo_study_uid": pseudo_study_uid,
                "n_series": len(batch.series),
                "n_frames": sum(s.frame_count for s in batch.series),
                "skipped_reason": batch.reason if batch.skipped else None,
            },
        )
        self._emit_audit(
            "preview.completed" if not batch.skipped else "preview.skipped",
            target={"pseudo_study_uid": pseudo_study_uid},
            meta={
                "n_series": len(batch.series),
                "n_frames": sum(s.frame_count for s in batch.series),
                "skipped_reason": batch.reason if batch.skipped else None,
            },
        )
        return preview_dict


    # ---- metadata-only (Flow A) QIDO-only fast-path ----

    def _process_study_metadata_only(
        self,
        study: StudySummary,
        *,
        original_uid: str,
        started: datetime,
        dry_run: bool,
    ) -> StudyOutcome:
        """gateway-flow-a-qido: build + upload the Flow A manifest from QIDO.

        Flow A's manifest only needs study-level counters (pseudo UID,
        modalities, n_instances) plus a ruleset-scoped method code sequence.
        None of those require per-instance tag inspection, so the pipeline
        skips the WADO metadata pull, the de-id engine, and every disk
        write. Per-study latency on a 192-slice Orthanc study drops from
        ~14 s (WADO metadata + Part-10 materialise + de-id) to ~0.3 s
        (one QIDO row + JSON POST).

        Pixel-level de-identification and burn-in handling are deferred to
        Flow B (ARCHITECTURE.md §4), invoked when an order-fulfillment
        request asks the Gateway for actual pixels.
        """
        # Derive the pseudo study UID up-front. Reusing :meth:`DeidEngine.pseudo_uid`
        # keeps Flow A and Flow B bit-compatible on the same original UID —
        # both end up resolving to the same pseudo row via the SQLite uid_map.
        try:
            pseudo_uid = self._deid.pseudo_uid(original_uid, "study")
        except Exception as exc:  # pragma: no cover — salt / db failure
            log.exception("flow_a: pseudo uid derivation failed")
            self._emit_audit(
                "pacs.fetch.failed",
                meta={"error": str(exc), "mode": "metadata_only"},
                target={"original_study_uid_hash": _short_hash(original_uid)},
            )
            return StudyOutcome(
                original_study_uid=original_uid,
                pseudo_study_uid=None,
                state=StudyState.FAILED_FETCH,
                reason=str(exc),
                duration_ms=_elapsed_ms(started),
            )

        # QIDO fast-path. ``fetch_study_qido_summary`` is the only PACS call
        # Flow A makes — no WADO traffic, no per-instance pulls.
        try:
            summary = self._pacs.fetch_study_qido_summary(original_uid)
        except PacsError as exc:
            self._emit_audit(
                "pacs.fetch.failed",
                meta={
                    "error": str(exc),
                    "status_code": exc.status_code,
                    "mode": "metadata_only",
                },
                target={"original_study_uid_hash": _short_hash(original_uid)},
            )
            return StudyOutcome(
                original_study_uid=original_uid,
                pseudo_study_uid=pseudo_uid,
                state=StudyState.FAILED_FETCH,
                reason=str(exc),
                duration_ms=_elapsed_ms(started),
            )
        fetch_ms = summary.duration_ms
        self._emit_audit(
            "pacs.fetch.completed",
            target={"original_study_uid_hash": _short_hash(original_uid)},
            meta={
                "n_instances": summary.n_instances,
                "n_series": summary.n_series,
                "bytes": 0,
                "duration_ms": fetch_ms,
                "mode": "metadata_only",
                "source": "qido",
            },
        )

        # Prefer modalities from the QIDO row (authoritative per-study) but
        # fall back to the ``query_studies`` summary when QIDO omitted the
        # tag — some mini DICOMweb stacks (notably dcm4chee in minimal
        # profile) return ``ModalitiesInStudy`` only on the list endpoint.
        modalities = summary.modalities or list(study.modalities_in_study)

        # Flow A does not run the de-id engine, so the method code sequence
        # is a ruleset-scoped static declaration rather than a per-instance
        # derivation. :func:`resolve_flow_a_method_codes` raises when the
        # ruleset has no mapping — surface as FAILED_FETCH so the sync loop
        # continues with other studies rather than aborting the whole run.
        try:
            method_codes = resolve_flow_a_method_codes(self._cfg.deid.ruleset_version)
        except ValueError as exc:
            self._emit_audit(
                "deid.failed",
                target={"pseudo_study_uid": pseudo_uid},
                meta={"error": str(exc), "mode": "metadata_only"},
            )
            return StudyOutcome(
                original_study_uid=original_uid,
                pseudo_study_uid=pseudo_uid,
                state=StudyState.FAILED_DEID,
                reason=str(exc),
                duration_ms=_elapsed_ms(started),
                fetch_ms=fetch_ms,
            )

        # Persist a study_job row so ``gateway status`` counts reflect this
        # Flow A study even though the pipeline never wrote a staging payload
        # nor invoked the de-id engine. We mark DEIDED → UPLOADING → UPLOADED
        # to preserve the same state-machine trace as Flow B (central's
        # ``gateway status`` dashboards key off these transitions).
        self._db.upsert_study_job(
            pseudo_uid,
            state=StudyState.DEIDED,
            modalities=modalities,
            n_instances=summary.n_instances,
            n_bytes=0,
        )
        self._db.mark_state(pseudo_uid, StudyState.DEIDED)
        self._emit_audit(
            "staging.skipped",
            target={"pseudo_study_uid": pseudo_uid},
            meta={
                "mode": "metadata_only",
                "n_instances": summary.n_instances,
                "source": "qido",
            },
        )

        if dry_run:
            self._emit_audit(
                "upload.skipped",
                target={"pseudo_study_uid": pseudo_uid},
                meta={"reason": "dry_run", "mode": "metadata_only"},
            )
            return StudyOutcome(
                original_study_uid=original_uid,
                pseudo_study_uid=pseudo_uid,
                state=StudyState.DEIDED,
                reason="dry_run",
                duration_ms=_elapsed_ms(started),
                fetch_ms=fetch_ms,
            )

        manifest = self._upload.build_metadata_only_manifest(
            gateway_id=self._cfg.agent.gateway_id,
            hospital_id=self._cfg.agent.hospital_id,
            pseudo_study_uid=pseudo_uid,
            modalities=modalities,
            ruleset_version=self._cfg.deid.ruleset_version,
            salt_version=self._cfg.deid.salt_version,
            method_codes=method_codes,
            n_instances=summary.n_instances,
            total_bytes=0,
        )
        self._emit_audit(
            "upload.started",
            target={"pseudo_study_uid": pseudo_uid},
            meta={
                "n_files": 0,
                "bytes": 0,
                "mode": "metadata_only",
                "n_instances": summary.n_instances,
            },
        )
        self._db.mark_state(pseudo_uid, StudyState.UPLOADING)
        upload_started = datetime.now()
        try:
            result = self._upload.upload_study_metadata_only(manifest)
        except UploadError as exc:
            self._emit_audit(
                "upload.failed",
                target={"pseudo_study_uid": pseudo_uid},
                meta={
                    "error": str(exc),
                    "status_code": exc.status_code,
                    "mode": "metadata_only",
                },
            )
            self._db.mark_state(pseudo_uid, StudyState.FAILED_UPLOAD, last_error=str(exc))
            self._db.schedule_retry(
                pseudo_uid,
                (datetime.now(tz=UTC) + timedelta(minutes=5)).isoformat(),
            )
            return StudyOutcome(
                original_study_uid=original_uid,
                pseudo_study_uid=pseudo_uid,
                state=StudyState.FAILED_UPLOAD,
                reason=str(exc),
                duration_ms=_elapsed_ms(started),
                fetch_ms=fetch_ms,
            )
        upload_ms = _elapsed_ms(upload_started)
        self._emit_audit(
            "upload.completed",
            target={"pseudo_study_uid": pseudo_uid},
            meta={
                "central_job_id": result.job_id,
                "bytes": 0,
                "duration_ms": upload_ms,
                "mode": "metadata_only",
            },
        )
        self._db.upsert_study_job(
            pseudo_uid,
            state=StudyState.UPLOADED,
            modalities=modalities,
            n_instances=summary.n_instances,
            n_bytes=0,
            central_job_id=result.job_id,
        )
        # Persist the original-UID hash alongside the UPLOADED mark so the
        # next sync can short-circuit via ``is_study_uploaded`` —
        # gateway-sync-skip-uploaded, Flow A.
        self._db.mark_state(
            pseudo_uid, StudyState.UPLOADED, original_uid=original_uid
        )
        self._db.clear_retry(pseudo_uid)
        return StudyOutcome(
            original_study_uid=original_uid,
            pseudo_study_uid=pseudo_uid,
            state=StudyState.UPLOADED,
            duration_ms=_elapsed_ms(started),
            fetch_ms=fetch_ms,
            deid_ms=0,
            upload_ms=upload_ms,
        )


def _sample_pixel_context(staging_dir: Path) -> tuple[str, str | None]:
    """Read StudyDescription + BodyPartExamined from the first staged DICOM.

    Returns ``("", None)`` on any error. The pixel engine tolerates empty
    values — they simply make the study exclusion/body-part gates fall
    through to SKIP.
    """
    try:
        import pydicom
    except ImportError:
        return "", None
    for path in sorted(Path(staging_dir).rglob("*.dcm")):
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=False)
        except Exception:
            continue
        return (
            str(getattr(ds, "StudyDescription", "") or ""),
            str(getattr(ds, "BodyPartExamined", "") or "") or None,
        )
    return "", None


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now() - start).total_seconds() * 1000)


def _short_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _method_codes(cfg: GatewayConfig) -> list[str]:
    codes = ["113100"]
    if cfg.deid.retain_options.longitudinal_dates:
        codes.append("113107")
    if cfg.deid.retain_options.patient_characteristics:
        codes.append("113108")
    if cfg.deid.retain_options.clean_descriptors:
        codes.append("113105")
    return codes
