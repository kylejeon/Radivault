"""Per-ingest audit event writer (dev-spec FR-55/FR-56)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from radivault_central.db.repository import insert_ingest_event


def record_ingest_event(
    session: Session,
    *,
    hospital_pk: int,
    gateway_id: str,
    event: str,
    status_code: int,
    request_id: str,
    central_job_id: str | None = None,
    pseudo_study_uid: str | None = None,
    error_code: str | None = None,
    bytes_received: int | None = None,
    duration_ms: int | None = None,
) -> None:
    """Append a row to ``audit_ingest_event`` (no PHI — dev-spec §6.7)."""
    insert_ingest_event(
        session,
        hospital_pk=hospital_pk,
        gateway_id=gateway_id,
        central_job_id=central_job_id,
        event=event,
        pseudo_study_uid=pseudo_study_uid,
        status_code=status_code,
        error_code=error_code,
        request_id=request_id,
        bytes_received=bytes_received,
        duration_ms=duration_ms,
    )
