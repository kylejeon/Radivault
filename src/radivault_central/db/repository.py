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
        session.scalar(select(Study.study_pk).where(Study.pseudo_study_uid == pseudo_study_uid))
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
    study_date_shifted: object | None = None,
    patient_sex: str | None = None,
    patient_age_bucket: int | None = None,
    preview_status: str | None = None,
    preview_thumbnail_key: str | None = None,
    raw_dicom_tags: dict | None = None,
) -> Study:
    """Create or upsert Study + Series + Instance rows inside the caller's transaction.

    metadata-thumbnail-ingest FR-INGEST-1 — also persists the v2 study root
    fields (study_date_shifted, manufacturer/model, body_part) and propagates
    sex/age_bucket onto the patient_pseudo row so the search facets aggregator
    can group on them.
    """
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
                sex=patient_sex,
                age_bucket=patient_age_bucket,
            )
            session.add(pp)
            session.flush()
        else:
            # idempotent re-ingest — refresh sex/age_bucket on existing row.
            if patient_sex is not None and pp.sex is None:
                pp.sex = patient_sex
            if patient_age_bucket is not None and pp.age_bucket is None:
                pp.age_bucket = patient_age_bucket
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
        study_date_shifted=study_date_shifted,
        central_job_id=central_job_id,
        gateway_id=gateway_id,
        ingested_at=datetime.now(tz=UTC),
        raw_dicom_tags=raw_dicom_tags,
    )
    if preview_status is not None:
        study.preview_status = preview_status
    if preview_thumbnail_key is not None:
        study.preview_thumbnail_key = preview_thumbnail_key
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


def upsert_study_v2(
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
    study_date_shifted: object | None,
    patient_sex: str | None,
    patient_age_bucket: int | None,
    pseudo_patient_key: str | None,
    preview_status: str | None,
    preview_thumbnail_key: str | None,
    raw_dicom_tags: dict | None,
) -> Study:
    """Idempotent UPDATE-or-INSERT for re-ingest / backfill paths.

    Used by ``radivault-gateway reingest`` (FR-BACKFILL-1) so re-running on the
    same pseudo_study_uid simply refreshes the v2 fields without violating the
    ``study.pseudo_study_uid`` UNIQUE constraint. Series / Instance rows are
    NOT touched (the original ingest already wrote them) — backfill only
    targets the v2 metadata + thumbnail key.
    """
    existing = session.scalar(
        select(Study).where(Study.pseudo_study_uid == pseudo_study_uid)
    )
    if existing is None:
        return insert_study_full(
            session,
            hospital=hospital,
            pseudo_study_uid=pseudo_study_uid,
            gateway_id=gateway_id,
            central_job_id=central_job_id,
            n_instances=n_instances,
            n_series=n_series,
            total_bytes=total_bytes,
            modality=modality,
            body_part=body_part,
            manufacturer=manufacturer,
            model_name=model_name,
            pseudo_patient_key=pseudo_patient_key,
            series_entries=[],
            study_date_shifted=study_date_shifted,
            patient_sex=patient_sex,
            patient_age_bucket=patient_age_bucket,
            preview_status=preview_status,
            preview_thumbnail_key=preview_thumbnail_key,
            raw_dicom_tags=raw_dicom_tags,
        )

    if body_part is not None:
        existing.body_part = body_part
    if manufacturer is not None:
        existing.manufacturer = manufacturer
    if model_name is not None:
        existing.model_name = model_name
    if study_date_shifted is not None:
        existing.study_date_shifted = study_date_shifted
    if modality is not None and existing.modality is None:
        existing.modality = modality
    if raw_dicom_tags is not None:
        existing.raw_dicom_tags = raw_dicom_tags
    if preview_thumbnail_key is not None:
        existing.preview_thumbnail_key = preview_thumbnail_key
    if preview_status is not None and existing.preview_status not in (
        "verified",
        "phi_detected",
    ):
        # FR-INGEST-1 idempotency: never downgrade a manually-verified row.
        existing.preview_status = preview_status

    if existing.patient_pseudo_pk is None and pseudo_patient_key:
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
                sex=patient_sex,
                age_bucket=patient_age_bucket,
            )
            session.add(pp)
            session.flush()
        existing.patient_pseudo_pk = pp.patient_pseudo_pk
    elif existing.patient_pseudo_pk is not None:
        pp = session.get(PatientPseudo, existing.patient_pseudo_pk)
        if pp is not None:
            if patient_sex is not None and pp.sex is None:
                pp.sex = patient_sex
            if patient_age_bucket is not None and pp.age_bucket is None:
                pp.age_bucket = patient_age_bucket
    session.flush()
    return existing


def insert_study_metadata_only(
    session: Session,
    *,
    hospital: Hospital,
    pseudo_study_uid: str,
    gateway_id: str,
    central_job_id: str,
    n_instances: int,
    total_bytes: int,
    modality: str | None,
    body_part: str | None = None,
    manufacturer: str | None = None,
    model_name: str | None = None,
    pseudo_patient_key: str | None = None,
) -> Study:
    """Insert a Study row with ``central_object_present=False`` (Flow A).

    Unlike :func:`insert_study_full`, no Series or Instance rows are written —
    the Gateway has not uploaded any pixel payload yet. The fulfillment
    subsystem (dev-spec-order-fulfillment §14 C-1) reads
    ``study.central_object_present`` to decide whether to fan out a
    transfer_job to the originating Gateway at order time.
    """
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
        n_series=0,
        total_bytes=total_bytes,
        modality=modality,
        body_part=body_part,
        manufacturer=manufacturer,
        model_name=model_name,
        central_job_id=central_job_id,
        gateway_id=gateway_id,
        ingested_at=datetime.now(tz=UTC),
        central_object_present=False,
    )
    session.add(study)
    session.flush()
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
