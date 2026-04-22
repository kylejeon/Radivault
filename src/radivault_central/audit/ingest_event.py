"""Per-ingest audit event writer (dev-spec FR-55/FR-56)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from radivault_central.db.repository import insert_ingest_event

log = logging.getLogger("radivault_central.audit.ingest_event")

SENTINEL_GATEWAY = "unknown"


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


def record_rejection(
    session_factory: Callable[[], Session],
    *,
    hospital_pk: int,
    gateway_id: str | None,
    status_code: int,
    error_code: str,
    request_id: str,
    pseudo_study_uid: str | None = None,
) -> None:
    """Best-effort ``ingest.rejected`` audit row (dev-spec FR-56).

    Writes a minimal row with no PHI and no manifest body — only the fields
    needed to demonstrate the rejection happened (``event_code``, ``error_code``,
    ``request_id``, ``hospital_pk``, ``received_at`` via server default). DB
    failures are logged and swallowed so we never double-fault the client.
    """
    try:
        with session_factory() as session:
            record_ingest_event(
                session,
                hospital_pk=hospital_pk,
                gateway_id=gateway_id or SENTINEL_GATEWAY,
                event="ingest.rejected",
                status_code=status_code,
                request_id=request_id,
                error_code=error_code,
                pseudo_study_uid=pseudo_study_uid,
            )
            session.commit()
    except Exception as exc:  # pragma: no cover — best-effort path
        # Log and continue — we still want the 4xx to reach the client.
        log.error(
            "audit_ingest_rejection_write_failed",
            extra={
                "event": "audit.write_failed",
                "error_code": error_code,
                "request_id": request_id,
                "detail": str(exc)[:200],
            },
        )
