"""Startup crash recovery for the v0.2 de-id-pixel pipeline.

Implements dev-spec FR-36 / AC-18: on gateway start, any ``study_job`` row
still in the ``pixel_processing`` state is the footprint of a process crash
during OCR or defacing. We rollback such rows to the last durable state
(``deided``) so the next poll tick re-queues them for the pixel stage.

Side-effects:
- Deletes partial staging artefacts under ``{staging_root}/{pseudo_study_uid}/``
  because the previous process may have written mid-OCR redaction output that
  is not safe to upload.
- Writes a ``pixel_audit_event`` row with op=``recovery``.
- Appends a ``pixel.recovery.applied`` event to the hash-chained audit log.
- Emits a WARN log line per recovered study.

The helper is safe to call when no orphaned rows exist (it simply returns 0).
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from radivault_gateway.audit import AuditLogger
from radivault_gateway.staging import StagingManager
from radivault_gateway.state import StateDB, StudyState

log = logging.getLogger("radivault.pipeline")


@dataclass(frozen=True)
class PixelRecoveryResult:
    recovered: int
    pseudo_study_uids: list[str]


def recover_orphaned_pixel_processing(
    db: StateDB,
    *,
    audit: AuditLogger,
    staging: StagingManager,
) -> PixelRecoveryResult:
    """Roll back ``pixel_processing`` rows to ``deided`` at startup (FR-36).

    Returns the number of rows recovered and their pseudo study UIDs.
    """
    jobs = db.list_study_jobs(state=StudyState.PIXEL_PROCESSING, limit=1000)
    if not jobs:
        return PixelRecoveryResult(recovered=0, pseudo_study_uids=[])

    pseudo_uids: list[str] = []
    for job in jobs:
        pseudo_uid = str(job.get("pseudo_study_uid") or "").strip()
        if not pseudo_uid:
            continue
        # Delete any partial staging artefacts so the next tick starts clean.
        staged_path = Path(staging.root) / pseudo_uid
        if staged_path.exists():
            shutil.rmtree(staged_path, ignore_errors=True)

        # Rollback state so the next poll tick re-queues via the pixel stage.
        db.mark_state(
            pseudo_uid,
            StudyState.DEIDED,
            last_error="startup_crash_recovery",
        )
        db.add_pixel_audit_event(
            pseudo_study_uid=pseudo_uid,
            op="recovery",
            outcome="rollback",
            reason="startup_crash_recovery",
        )
        record = audit.append(
            "pixel.recovery.applied",
            target={"pseudo_study_uid": pseudo_uid},
            meta={"from_state": "pixel_processing", "to_state": "deided"},
        )
        log.warning(
            "pixel.recovery.applied",
            extra={
                "event": "pixel.recovery.applied",
                "pseudo_study_uid": pseudo_uid,
                "pixel": {
                    "stage": "recovery",
                    "reason": "startup_crash_recovery",
                    "audit_seq": record.seq,
                },
            },
        )
        pseudo_uids.append(pseudo_uid)
    return PixelRecoveryResult(recovered=len(pseudo_uids), pseudo_study_uids=pseudo_uids)
