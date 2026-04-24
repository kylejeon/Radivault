"""``POST /v1/ingest/studies`` router (dev-spec §4.1, §8.1)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from ulid import ULID

from radivault_central.audit.ingest_event import record_ingest_event, record_rejection
from radivault_central.auth.middleware import require_hospital
from radivault_central.db.repository import (
    get_hospital_by_pk,
    insert_study_full,
    insert_study_metadata_only,
    study_exists,
)
from radivault_central.errors import (
    AuthMismatch,
    CentralError,
    IngestContentType,
    ManifestDuplicate,
    ManifestSchema,
    ManifestSha256,
    StorageWriteError,
    UnsupportedMedia,
)
from radivault_central.manifest.validator import ManifestValidator
from radivault_central.telemetry import (
    INGEST_BYTES,
    INGEST_DURATION,
    INGEST_INSTANCES,
    INGEST_REQUESTS,
    MANIFEST_REJECTIONS,
)

log = logging.getLogger("radivault_central.routers.ingest")
router = APIRouter()


def _peek_gateway_id(raw_manifest: bytes | None) -> str | None:
    """Best-effort gateway_id extraction — no PHI, no exceptions."""
    if not raw_manifest:
        return None
    try:
        decoded = json.loads(raw_manifest.decode("utf-8"))
    except Exception:
        return None
    val = decoded.get("gateway_id") if isinstance(decoded, dict) else None
    if isinstance(val, str) and val:
        return val[:64]
    return None


def _peek_pseudo_study_uid(raw_manifest: bytes | None) -> str | None:
    """Best-effort pseudo_study_uid extraction (already PHI-safe by construction)."""
    if not raw_manifest:
        return None
    try:
        decoded = json.loads(raw_manifest.decode("utf-8"))
    except Exception:
        return None
    val = decoded.get("pseudo_study_uid") if isinstance(decoded, dict) else None
    if isinstance(val, str) and val:
        return val[:256]
    return None


@router.post("/v1/ingest/studies", status_code=201)
async def post_ingest(request: Request) -> dict:
    content_type = request.headers.get("Content-Type", "")
    if not content_type.lower().startswith("multipart/"):
        raise IngestContentType()

    # Starlette defaults (max_files=1000, max_part_size=1MB) are too low for
    # DICOM studies: MR/CT series can exceed 1000 slices, and a single slice
    # can exceed 1MB. Per-hospital manifest validator still enforces
    # n_instances <= hospital.max_instances_per_study downstream.
    form = await request.form(max_files=50_000, max_part_size=64 * 1024 * 1024)
    manifest_upload = form.get("manifest")
    files = form.getlist("files")
    if manifest_upload is None:
        raise ManifestSchema(detail="manifest part missing")
    if not files:
        raise ManifestSchema(detail="no files uploaded")

    raw_manifest: bytes
    if hasattr(manifest_upload, "read"):
        raw = await manifest_upload.read()
        raw_manifest = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
    elif isinstance(manifest_upload, (bytes, bytearray)):
        raw_manifest = bytes(manifest_upload)
    elif isinstance(manifest_upload, str):
        raw_manifest = manifest_upload.encode("utf-8")
    else:  # pragma: no cover
        raise ManifestSchema(
            detail=f"manifest part unrecognised type: {type(manifest_upload).__name__}"
        )

    hospital_pk, hospital_id = require_hospital(request)
    session_factory = request.app.state.session_factory
    store = request.app.state.object_store
    env = request.app.state.env
    request_id = getattr(request.state, "request_id", "unknown")

    # FR-56: every rejected preflight must land as one ``ingest.rejected`` row
    # in ``audit_ingest_event``. We funnel every preflight failure through a
    # single try/except that calls ``record_rejection`` *before* re-raising.
    # The audit write carries only error_code / request_id / hospital_pk /
    # pseudo_study_uid — no PHI, no manifest body.
    manifest = None
    file_bodies: list[tuple[str, bytes, str]] = []  # (filename, data, sha256)
    total_received = 0
    started = time.time()
    try:
        # Load hospital row + validate manifest.
        with session_factory() as session:
            hospital = get_hospital_by_pk(session, hospital_pk)
            if hospital is None:
                raise AuthMismatch(detail="hospital row missing")
            validator = ManifestValidator(
                hospital=hospital,
                max_manifest_bytes=request.app.state.max_manifest_bytes,
            )
            manifest = validator.parse_and_validate(raw_manifest)
            if manifest.hospital_id != hospital_id:
                raise AuthMismatch(
                    detail=(
                        f"manifest.hospital_id={manifest.hospital_id!r} "
                        f"!= token.hospital_id={hospital_id!r}"
                    )
                )
            if study_exists(session, manifest.pseudo_study_uid):
                raise ManifestDuplicate(
                    detail=f"study already ingested: {manifest.pseudo_study_uid}"
                )

        # Read and validate file payloads before we touch storage.
        expected_map = {f.filename: f for f in manifest.files}
        for upload in files:
            if not hasattr(upload, "read"):
                raise ManifestSchema(detail=f"unexpected non-file part: {type(upload).__name__}")
            data = await upload.read()
            if isinstance(data, str):
                data = data.encode("utf-8")
            digest = hashlib.sha256(data).hexdigest()
            expected = expected_map.get(upload.filename)
            if expected is None or expected.sha256.lower() != digest.lower():
                raise ManifestSha256(detail=f"sha256 mismatch for {upload.filename}")
            file_bodies.append((upload.filename, data, digest))
            total_received += len(data)

        if len(file_bodies) != len(manifest.files):
            raise ManifestSha256(detail="file count mismatch with manifest")
    except CentralError as exc:
        code = exc.code
        MANIFEST_REJECTIONS.labels(hospital_id=hospital_id, error_code=code).inc()
        INGEST_REQUESTS.labels(hospital_id=hospital_id, status="rejected").inc()
        # Prefer manifest's parsed fields when available; fall back to a
        # best-effort peek of the raw bytes. Never echo the full body.
        gateway_id = manifest.gateway_id if manifest is not None else _peek_gateway_id(raw_manifest)
        study_uid = (
            manifest.pseudo_study_uid
            if manifest is not None
            else _peek_pseudo_study_uid(raw_manifest)
        )
        record_rejection(
            session_factory,
            hospital_pk=hospital_pk,
            gateway_id=gateway_id,
            status_code=exc.status_code,
            error_code=code,
            request_id=request_id,
            pseudo_study_uid=study_uid,
        )
        raise

    central_job_id = f"ingest_{ULID()!s}"
    hash2 = hashlib.sha256(manifest.pseudo_study_uid.encode()).hexdigest()[:2]
    key_prefix = (
        f"{env}/{hash2}/{hospital_id}/{manifest.pseudo_study_uid}/{manifest.pseudo_study_uid}"
    )
    uploaded_keys: list[str] = []
    try:
        for filename, data, _digest in file_bodies:
            key = f"{key_prefix}/{filename}"
            store.put_object(key, data, content_type="application/dicom")
            uploaded_keys.append(key)
        manifest_key = f"{key_prefix}/_manifest.json"
        store.put_object(manifest_key, raw_manifest, content_type="application/json")
        uploaded_keys.append(manifest_key)
    except Exception as exc:
        # Best-effort cleanup of whatever we wrote.
        try:
            store.delete_objects(uploaded_keys)
        except Exception:  # pragma: no cover — cleanup is best-effort only
            log.warning("storage_cleanup_fail")
        INGEST_REQUESTS.labels(hospital_id=hospital_id, status="rejected").inc()
        raise StorageWriteError(detail=str(exc)) from exc

    # DB commit.
    with session_factory() as session:
        hospital = get_hospital_by_pk(session, hospital_pk)
        assert hospital is not None
        series_entry = {
            "pseudo_series_uid": manifest.pseudo_study_uid + ".1",
            "modality": manifest.primary_modality(),
            "body_part": None,
            "series_number": 1,
            "instances": [
                {
                    "pseudo_sop_uid": manifest.pseudo_study_uid + f".1.{i + 1}",
                    "sop_class_uid": None,
                    "instance_number": i + 1,
                    "object_key": uploaded_keys[i],
                    "bytes": manifest.files[i].bytes,
                    "sha256": bytes.fromhex(manifest.files[i].sha256),
                }
                for i in range(len(manifest.files))
            ],
        }
        insert_study_full(
            session,
            hospital=hospital,
            pseudo_study_uid=manifest.pseudo_study_uid,
            gateway_id=manifest.gateway_id,
            central_job_id=central_job_id,
            n_instances=manifest.n_instances,
            n_series=1,
            total_bytes=manifest.total_bytes,
            modality=manifest.primary_modality(),
            body_part=None,
            manufacturer=None,
            model_name=None,
            pseudo_patient_key=None,
            series_entries=[series_entry],
        )
        duration_ms = int((time.time() - started) * 1000)
        record_ingest_event(
            session,
            hospital_pk=hospital_pk,
            gateway_id=manifest.gateway_id,
            event="ingest.accepted",
            status_code=201,
            request_id=request_id,
            central_job_id=central_job_id,
            pseudo_study_uid=manifest.pseudo_study_uid,
            bytes_received=total_received,
            duration_ms=duration_ms,
        )
        session.commit()

    INGEST_REQUESTS.labels(hospital_id=hospital_id, status="accepted").inc()
    INGEST_BYTES.labels(hospital_id=hospital_id).inc(total_received)
    INGEST_INSTANCES.labels(hospital_id=hospital_id).inc(manifest.n_instances)
    INGEST_DURATION.labels(hospital_id=hospital_id, outcome="accepted").observe(
        time.time() - started
    )

    return {
        "central_job_id": central_job_id,
        "job_id": central_job_id,  # FR-70 backwards-compat
        "received_at": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "object_keys": uploaded_keys,
    }


@router.post("/v1/ingest/studies/metadata", status_code=201)
async def post_ingest_metadata_only(request: Request) -> dict:
    """Accept a metadata-only manifest (Flow A — ARCHITECTURE.md §4).

    Accepts ``application/json`` only. No DICOM pixel payload is written to
    object storage; the study row lands in central DB with
    ``central_object_present=False`` so the fulfillment subsystem knows to
    fan out a transfer_job on order confirmation (Flow B).

    Idempotency contract is identical to ``/v1/ingest/studies``: callers MUST
    supply an ``Idempotency-Key``. Gateways SHOULD use a distinct key prefix
    (e.g. ``meta-<pseudo_study_uid>``) to avoid colliding with a full-payload
    upload of the same logical study.
    """
    content_type = request.headers.get("Content-Type", "")
    if not content_type.lower().startswith("application/json"):
        raise UnsupportedMedia(
            detail="/v1/ingest/studies/metadata requires application/json"
        )

    raw_manifest = await request.body()
    hospital_pk, hospital_id = require_hospital(request)
    session_factory = request.app.state.session_factory
    request_id = getattr(request.state, "request_id", "unknown")

    manifest = None
    started = time.time()
    try:
        with session_factory() as session:
            hospital = get_hospital_by_pk(session, hospital_pk)
            if hospital is None:
                raise AuthMismatch(detail="hospital row missing")
            validator = ManifestValidator(
                hospital=hospital,
                max_manifest_bytes=request.app.state.max_manifest_bytes,
            )
            manifest = validator.parse_and_validate_metadata_only(raw_manifest)
            if manifest.hospital_id != hospital_id:
                raise AuthMismatch(
                    detail=(
                        f"manifest.hospital_id={manifest.hospital_id!r} "
                        f"!= token.hospital_id={hospital_id!r}"
                    )
                )
            if study_exists(session, manifest.pseudo_study_uid):
                raise ManifestDuplicate(
                    detail=f"study already ingested: {manifest.pseudo_study_uid}"
                )
    except CentralError as exc:
        code = exc.code
        MANIFEST_REJECTIONS.labels(hospital_id=hospital_id, error_code=code).inc()
        INGEST_REQUESTS.labels(hospital_id=hospital_id, status="rejected").inc()
        gateway_id = (
            manifest.gateway_id if manifest is not None else _peek_gateway_id(raw_manifest)
        )
        study_uid = (
            manifest.pseudo_study_uid
            if manifest is not None
            else _peek_pseudo_study_uid(raw_manifest)
        )
        record_rejection(
            session_factory,
            hospital_pk=hospital_pk,
            gateway_id=gateway_id,
            status_code=exc.status_code,
            error_code=code,
            request_id=request_id,
            pseudo_study_uid=study_uid,
        )
        raise

    central_job_id = f"ingest_{ULID()!s}"
    # DB commit — study row only, no series/instance/S3.
    with session_factory() as session:
        hospital = get_hospital_by_pk(session, hospital_pk)
        assert hospital is not None
        insert_study_metadata_only(
            session,
            hospital=hospital,
            pseudo_study_uid=manifest.pseudo_study_uid,
            gateway_id=manifest.gateway_id,
            central_job_id=central_job_id,
            n_instances=manifest.n_instances,
            total_bytes=manifest.total_bytes,
            modality=manifest.primary_modality(),
        )
        duration_ms = int((time.time() - started) * 1000)
        record_ingest_event(
            session,
            hospital_pk=hospital_pk,
            gateway_id=manifest.gateway_id,
            event="central.ingest.metadata_only.completed",
            status_code=201,
            request_id=request_id,
            central_job_id=central_job_id,
            pseudo_study_uid=manifest.pseudo_study_uid,
            bytes_received=len(raw_manifest),
            duration_ms=duration_ms,
        )
        session.commit()

    INGEST_REQUESTS.labels(hospital_id=hospital_id, status="accepted").inc()
    # Metadata-only ingest does not move pixel bytes; we count manifest bytes
    # so the per-hospital telemetry still reflects incoming traffic.
    INGEST_BYTES.labels(hospital_id=hospital_id).inc(len(raw_manifest))
    INGEST_INSTANCES.labels(hospital_id=hospital_id).inc(manifest.n_instances)
    INGEST_DURATION.labels(hospital_id=hospital_id, outcome="accepted").observe(
        time.time() - started
    )

    return {
        "central_job_id": central_job_id,
        "job_id": central_job_id,
        "mode": "metadata_only",
        "received_at": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
