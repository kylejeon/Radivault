"""Thin repository helpers for Central Ingest DB access.

The repositories are intentionally stateless and take an explicit
``Session`` — callers own the transaction. This keeps tests trivial to write
against SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from radivault_central.db.models import (
    AuditAnchor,
    AuditIngestEvent,
    AuthToken,
    Hospital,
    IngestIdempotencyMirror,
    Instance,
    PatientPseudo,
    Series,
    Study,
)


def get_hospital_by_id(session: Session, hospital_id: str) -> Hospital | None:
    return session.scalar(select(Hospital).where(Hospital.hospital_id == hospital_id))


def get_hospital_by_pk(session: Session, hospital_pk: int) -> Hospital | None:
    return session.get(Hospital, hospital_pk)


def list_tokens_for_hospital(session: Session, hospital_pk: int) -> list[AuthToken]:
    return list(
        session.scalars(select(AuthToken).where(AuthToken.hospital_pk == hospital_pk)).all()
    )


def get_token_by_kid(session: Session, kid: str) -> AuthToken | None:
    return session.scalar(select(AuthToken).where(AuthToken.token_kid == kid))


def latest_anchor(session: Session, hospital_pk: int) -> AuditAnchor | None:
    return session.scalar(
        select(AuditAnchor)
        .where(AuditAnchor.hospital_pk == hospital_pk)
        .order_by(AuditAnchor.anchored_at.desc())
        .limit(1)
    )


def study_exists(session: Session, pseudo_study_uid: str) -> bool:
    return (
        session.scalar(
            select(Study.study_pk).where(Study.pseudo_study_uid == pseudo_study_uid)
        )
        is not None
    )


def insert_study_full(
    session: Session,
    *,
    hospital: Hospital,
    pseudo_study_uid: str,
    gateway_id: str,
    central_job_id: str,
    n_instances: int,
    n_series: int,
    total_bytes: int,
    modality: str | None,
    body_part: str | None,
    manufacturer: str | None,
    model_name: str | None,
    pseudo_patient_key: str | None,
    series_entries: list[dict],
) -> Study:
    """Create Study + Series + Instance rows inside the caller's transaction."""
    patient_pk: int | None = None
    if pseudo_patient_key:
        pp = session.scalar(
            select(PatientPseudo).where(
                PatientPseudo.hospital_pk == hospital.hospital_pk,
                PatientPseudo.pseudo_patient_key == pseudo_patient_key,
            )
        )
        if pp is None:
            pp = PatientPseudo(
                hospital_pk=hospital.hospital_pk,
                pseudo_patient_key=pseudo_patient_key,
            )
            session.add(pp)
            session.flush()
        patient_pk = pp.patient_pseudo_pk

    study = Study(
        pseudo_study_uid=pseudo_study_uid,
        hospital_pk=hospital.hospital_pk,
        patient_pseudo_pk=patient_pk,
        n_instances=n_instances,
        n_series=n_series,
        total_bytes=total_bytes,
        modality=modality,
        body_part=body_part,
        manufacturer=manufacturer,
        model_name=model_name,
        central_job_id=central_job_id,
        gateway_id=gateway_id,
        ingested_at=datetime.now(tz=UTC),
    )
    session.add(study)
    session.flush()

    for s in series_entries:
        series_row = Series(
            study_pk=study.study_pk,
            pseudo_series_uid=s["pseudo_series_uid"],
            modality=s.get("modality"),
            body_part=s.get("body_part"),
            series_number=s.get("series_number"),
            n_instances=len(s["instances"]),
        )
        session.add(series_row)
        session.flush()
        for inst in s["instances"]:
            session.add(
                Instance(
                    series_pk=series_row.series_pk,
                    pseudo_sop_uid=inst["pseudo_sop_uid"],
                    sop_class_uid=inst.get("sop_class_uid"),
                    instance_number=inst.get("instance_number"),
                    object_key=inst["object_key"],
                    bytes=inst["bytes"],
                    sha256=inst["sha256"],
                )
            )
    return study


def insert_ingest_event(
    session: Session,
    *,
    hospital_pk: int,
    gateway_id: str,
    central_job_id: str | None,
    event: str,
    pseudo_study_uid: str | None,
    status_code: int,
    error_code: str | None,
    request_id: str,
    bytes_received: int | None,
    duration_ms: int | None,
) -> AuditIngestEvent:
    row = AuditIngestEvent(
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
    session.add(row)
    session.flush()
    return row


def upsert_idempotency_mirror(
    session: Session,
    *,
    key: str,
    hospital_pk: int,
    response_sha256: bytes,
    response_status_code: int,
    response_body: str | None,
) -> IngestIdempotencyMirror:
    existing = session.get(IngestIdempotencyMirror, {"key": key, "hospital_pk": hospital_pk})
    if existing is not None:
        return existing
    row = IngestIdempotencyMirror(
        key=key,
        hospital_pk=hospital_pk,
        response_sha256=response_sha256,
        response_status_code=response_status_code,
        response_body=response_body,
    )
    session.add(row)
    session.flush()
    return row


def get_idempotency_mirror(
    session: Session, *, key: str, hospital_pk: int
) -> IngestIdempotencyMirror | None:
    return session.get(IngestIdempotencyMirror, {"key": key, "hospital_pk": hospital_pk})
