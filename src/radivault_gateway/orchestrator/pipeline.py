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

from radivault_gateway.audit import AuditLogger
from radivault_gateway.config import GatewayConfig
from radivault_gateway.deid import DeidEngine, QuarantineRequired
from radivault_gateway.deid.pixel import (
    PixelDeidEngine,
    PixelDeidResult,
    PixelQuarantineRequired,
)
from radivault_gateway.pacs import DicomWebPacsClient, PacsError, StudySummary
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

    def run_once(
        self,
        *,
        since: date | None = None,
        until: date | None = None,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> RunSummary:
        """Perform one full sync cycle. Returns a summary with per-study outcomes."""
        summary = RunSummary()

        if self._staging.backpressure_triggered():
            log.warning(
                "staging backpressure active; skipping fetch",
                extra={"usage_pct": round(self._staging.disk_usage_pct(), 1)},
            )
            self._audit.append(
                "staging.backpressure",
                meta={"usage_pct": round(self._staging.disk_usage_pct(), 1)},
            )
            return summary

        today = date.today()
        if until is None:
            until = today
        if since is None:
            since = today - timedelta(days=self._cfg.pacs.query.lookback_days)

        self._audit.append(
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
            self._audit.append(
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
            outcome = self._process_study(study, dry_run=dry_run)
            summary.outcomes.append(outcome)
            if outcome.state == StudyState.UPLOADED:
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

    def _process_study(self, study: StudySummary, *, dry_run: bool) -> StudyOutcome:
        started = datetime.now()
        original_uid = study.study_instance_uid
        pseudo_uid: str | None = None
        fetch_dir: Path | None = None
        try:
            fetch_dir = Path(tempfile.mkdtemp(prefix="radivault_fetch_"))
            fetch_started = datetime.now()
            try:
                fetch = self._pacs.fetch_study(original_uid, fetch_dir)
            except PacsError as exc:
                self._audit.append(
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
            self._audit.append(
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
            self._audit.append(
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
                self._audit.append(
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
                self._audit.append(
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
            self._audit.append(
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
                self._audit.append(
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
            self._audit.append(
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
                self._audit.append(
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
            )
            self._audit.append(
                "upload.started",
                target={"pseudo_study_uid": pseudo_uid},
                meta={"n_files": len(staged_files), "bytes": manifest["total_bytes"]},
            )
            self._db.mark_state(pseudo_uid, StudyState.UPLOADING)
            upload_started = datetime.now()
            try:
                result = self._upload.upload_study(manifest, staged_files)
            except UploadError as exc:
                self._audit.append(
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
            self._audit.append(
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
            self._db.mark_state(pseudo_uid, StudyState.UPLOADED)
            self._db.clear_retry(pseudo_uid)

            # Cleanup staging (FR-15)
            if self._staging.cleanup_study(pseudo_uid):
                self._audit.append(
                    "staging.cleanup",
                    target={"pseudo_study_uid": pseudo_uid},
                    meta={},
                )
            else:
                self._audit.append(
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
            self._audit.append(
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
                self._audit.append(
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
        self._audit.append(
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
            },
        )
        self._db.add_pixel_audit_event(
            pseudo_study_uid=pseudo_uid,
            op="triage",
            outcome="success",
            reason=result.decision,
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
            )
        if result.defacing_applied:
            self._db.add_pixel_audit_event(
                pseudo_study_uid=pseudo_uid,
                op="deface",
                outcome="success",
                library=result.library_deface,
                duration_ms=result.deface_duration_ms,
                removed_voxel_ratio=result.removed_voxel_ratio,
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
