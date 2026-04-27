"""``POST /v1/ingest/studies`` router (dev-spec §4.1, §8.1).

metadata-thumbnail-ingest FR-INGEST-1 — v2 manifest persistence:
- study row is populated with body_part / manufacturer / model_name /
  study_date_shifted (from manifest v2 root fields).
- patient_pseudo row is populated with sex / age_bucket so the search
  facets aggregator can group on them.
- thumbnail (base64 in manifest.thumbnail.data_b64) is written to MinIO
  as ``radivault-preview/thumbnails/{pseudo_study_uid}.jpg`` and the
  preview_status is bumped to ``auto_verified`` when phi_scrub_status="passed".
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import time
from datetime import UTC, date, datetime

from fastapi import APIRouter, Request
from sqlalchemy import select
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


def _age_bucket_to_int(label: str | None) -> int | None:
    """metadata-thumbnail-ingest FR-INGEST-1: convert "30-34" / "90+" to int.

    The patient_pseudo.age_bucket column is SmallInteger storing the lower
    bound of the bucket (30 for "30-34", 90 for "90+"). The search facets
    aggregator stringifies it back via str(value).
    """
    if not label:
        return None
    label = label.strip()
    if label.endswith("+"):
        try:
            return int(label[:-1])
        except ValueError:
            return None
    if "-" in label:
        try:
            return int(label.split("-", 1)[0])
        except ValueError:
            return None
    return None


def _parse_iso_date(val: str | None):
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except (TypeError, ValueError):
        return None


def _record_quarantine(session, *, study_pk: int, scrub_meta: dict) -> None:
    """text-search-description Phase 1.5 FR-TS15-10 — append quarantine audit.

    Inserts one row into ``study_phi_quarantine_audit`` with the scrub
    metadata reported by the gateway. Pure SQL via session.execute so this
    works on both Postgres (text[] columns) and SQLite (text fallback).
    """
    from sqlalchemy import text as _sql_text

    bind = session.get_bind()
    is_pg = bind.dialect.name == "postgresql" if bind is not None else False

    blacklist = list(scrub_meta.get("blacklist_matched") or [])
    whitelist = list(scrub_meta.get("whitelist_matched") or [])
    suspicious = int(scrub_meta.get("suspicious_token_count") or 0)
    scrub_version = str(scrub_meta.get("scrub_version") or "unknown")
    before_hash = str(scrub_meta.get("before_hash") or "")
    after_hash = str(scrub_meta.get("after_hash") or "")

    if is_pg:
        session.execute(
            _sql_text(
                """
                INSERT INTO study_phi_quarantine_audit
                  (study_pk, scrub_version, blacklist_matched,
                   whitelist_matched, suspicious_token_count,
                   before_hash, after_hash)
                VALUES
                  (:study_pk, :sv, CAST(:bl AS text[]), CAST(:wl AS text[]),
                   :stc, :bh, :ah)
                """
            ),
            {
                "study_pk": study_pk,
                "sv": scrub_version,
                "bl": "{" + ",".join(f'"{b}"' for b in blacklist) + "}",
                "wl": "{" + ",".join(f'"{w}"' for w in whitelist) + "}",
                "stc": suspicious,
                "bh": before_hash,
                "ah": after_hash,
            },
        )
    else:
        # SQLite test fallback — TEXT columns, JSON-encoded arrays.
        import json as _json

        session.execute(
            _sql_text(
                """
                INSERT INTO study_phi_quarantine_audit
                  (study_pk, scrub_version, blacklist_matched,
                   whitelist_matched, suspicious_token_count,
                   before_hash, after_hash)
                VALUES
                  (:study_pk, :sv, :bl, :wl, :stc, :bh, :ah)
                """
            ),
            {
                "study_pk": study_pk,
                "sv": scrub_version,
                "bl": _json.dumps(blacklist),
                "wl": _json.dumps(whitelist),
                "stc": suspicious,
                "bh": before_hash,
                "ah": after_hash,
            },
        )


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


def _persist_preview_batch(
    session,
    *,
    pseudo_study_uid: str,
    manifest_preview,
) -> None:
    """jpg-preview-defacing FR-PREVIEW-12 / FR-PREVIEW-13 / FR-AUDIT-1.

    Persist the gateway-emitted ``manifest.preview`` block into the
    central DB. Three writes per series, all within the caller's
    transaction so partial failure is impossible:

      1. UPDATE series.preview_* WHERE pseudo_series_uid=...
      2. DELETE + INSERT N rows into dicom_preview_frame for the series
         (DELETE first by ``(pseudo_series_uid, frame_idx)`` so a
         retry / resync doesn't dup-insert — the table has a UNIQUE
         constraint on the same pair).
      3. INSERT 1 row into phi_scrub_audit per series (append-only).

    ``manifest_preview`` is a :class:`PreviewBatch` Pydantic model. When
    it's None or ``skipped=True`` the function is a no-op.
    """
    if manifest_preview is None:
        return
    if getattr(manifest_preview, "skipped", False):
        # FR-PREVIEW-3: flag-off ingest carries skipped=True; nothing to
        # persist, but it's NOT an error.
        return

    from datetime import datetime as _dt

    from radivault_central.db.models import (
        DicomPreviewFrame,
        PhiScrubAudit,
        Series,
    )

    pipeline_version = (
        getattr(manifest_preview, "pipeline_version", None) or "0.1.0"
    )
    now = _dt.now(tz=UTC)

    for series in manifest_preview.series or []:
        pseudo_series_uid = series.pseudo_series_uid
        # 1) UPDATE series.preview_* by pseudo_series_uid. Series row
        # was created earlier in the same transaction by
        # ``insert_study_full``. We do not INSERT here because the
        # gateway might emit a preview entry for a series that does not
        # exist (impossible by contract but defensive: log + skip).
        series_row = session.scalar(
            select(Series).where(Series.pseudo_series_uid == pseudo_series_uid)
        )
        if series_row is None:
            log.warning(
                "preview_persist_series_missing",
                extra={
                    "event": "ingest.preview.series_missing",
                    "pseudo_series_uid": pseudo_series_uid,
                },
            )
            continue
        series_row.preview_status = series.preview_status
        series_row.preview_frame_count = int(series.frame_count or 0)
        series_row.preview_deface_decision = series.deface_decision
        series_row.preview_deface_method = series.phi_scrub_method
        series_row.preview_pipeline_version = pipeline_version
        if series.preview_status == "generated":
            series_row.preview_generated_at = now

        # 2) DICOM preview frames — idempotent re-ingest via DELETE-then-
        # INSERT. The UNIQUE(pseudo_series_uid, frame_idx) constraint
        # on dicom_preview_frame would otherwise raise on retry.
        if series.frames:
            session.query(DicomPreviewFrame).filter(
                DicomPreviewFrame.pseudo_series_uid == pseudo_series_uid
            ).delete(synchronize_session=False)
            for frame in series.frames:
                session.add(
                    DicomPreviewFrame(
                        pseudo_series_uid=pseudo_series_uid,
                        pseudo_study_uid=pseudo_study_uid,
                        frame_idx=int(frame.frame_idx),
                        minio_key=frame.minio_key,
                        width=int(frame.width),
                        height=int(frame.height),
                        byte_size=int(frame.byte_size),
                        sha256=frame.sha256,
                        phi_scrub_method=frame.phi_scrub_method,
                        source_instance_uid_pseudo=(
                            frame.source_instance_uid_pseudo
                        ),
                    )
                )

        # 3) PHI scrub audit — append-only. One row per (series, ingest).
        # Re-ingest produces multiple rows; the search-side manifest
        # endpoint picks the latest by max(id) so this is by design.
        session.add(
            PhiScrubAudit(
                pseudo_study_uid=pseudo_study_uid,
                pseudo_series_uid=pseudo_series_uid,
                modality=(series.modality or "?")[:8],
                body_part=(
                    series.body_part[:32] if series.body_part else None
                ),
                deface_decision=series.deface_decision or "not_required",
                deface_decision_reason=(
                    series.deface_decision_reason or ""
                )[:255],
                phi_scrub_method=(series.phi_scrub_method or "")[:40],
                sidecar_image_tag=(
                    series.sidecar_image_tag[:64]
                    if series.sidecar_image_tag
                    else None
                ),
                afni_version=(
                    series.afni_version[:32]
                    if series.afni_version
                    else None
                ),
                duration_ms=series.duration_ms,
                outcome=series.outcome,
                error_code=(
                    series.error_code[:40] if series.error_code else None
                ),
                error_detail=_scrub_audit_error_detail(series.error_detail),
                pipeline_version=pipeline_version[:32],
            )
        )


# HIGH #5 — PHI-free ``error_detail`` enforcement (jpg-preview-defacing
# AC-19 / FR-AUDIT-3). Allow-list of strings the sidecar / gateway are
# expected to emit. Anything else with >2 consecutive digits is replaced
# with the literal ``"redacted_by_phi_guard"`` and a warning is logged.
#
# The sidecar's known error codes are listed in
# ``docker/afni-refacer/app.py`` + ``radivault_gateway/deface_client.py``;
# they are short ASCII strings without patient identifiers. The regex
# guard only targets long digit runs because that is the most common
# PHI shape (MRN, phone, RRN). Letters + short codes pass freely so
# legitimate strings like "AFNI exceeded 600s" still survive.
_PHI_DIGIT_RUN = re.compile(r"\d{3,}")
_AUDIT_DETAIL_ALLOWLIST = frozenset(
    {
        # Sidecar-emitted (docker/afni-refacer/app.py) — exact literals
        # that contain digit runs by design.
        # We don't enumerate every possibility; instead we validate
        # shape: 3+ consecutive digits is suspicious unless explicitly
        # allow-listed. The allow-list grows as needed.
    }
)


def _scrub_audit_error_detail(detail: str | None) -> str | None:
    """FR-AUDIT-3 / HIGH #5 enforcement.

    Returns the input verbatim when it's None / short / digit-light.
    Replaces with ``"redacted_by_phi_guard"`` (and logs) when the
    detail contains 3+ consecutive digits NOT matching an allow-listed
    pattern (timeouts, return codes — these have at most 1-2 digits in
    sequence).
    """
    if detail is None:
        return None
    if not isinstance(detail, str):
        # Defensive: pydantic should guarantee str, but if a future caller
        # passes a non-string we drop it rather than coerce.
        return None
    if len(detail) > 2000:
        detail = detail[:2000]
    # Sample of legitimate strings:
    #   "healthz != ok"                → no digits, ok
    #   "AFNI exceeded 600s"           → 1 digit run len=3 — currently flagged
    #                                    (acceptable: emit redacted, audit
    #                                    still records error_code separately)
    #   "client-side timeout 600s"     → same
    #   "tar error: ..."               → may include filenames; if so any
    #                                    digit run blocks it. OK.
    #   "afni dumped core"             → no digits, ok
    #
    # The conservative posture: any 3+ digit run that isn't in the
    # allow-list is replaced. error_code on the same row preserves the
    # diagnostic signal.
    if _AUDIT_DETAIL_ALLOWLIST:
        # Future hook — we don't currently allow-list any string
        # because the sidecar's debug strings have short digit runs.
        for allowed in _AUDIT_DETAIL_ALLOWLIST:
            if detail == allowed:
                return detail
    if _PHI_DIGIT_RUN.search(detail):
        log.warning(
            "audit_error_detail_redacted",
            extra={
                "event": "ingest.preview.error_detail_redacted",
                "len": len(detail),
            },
        )
        return "redacted_by_phi_guard"
    return detail


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

    # metadata-thumbnail-ingest FR-INGEST-1: read v2 manifest fields (all
    # Optional — v1 manifests pass the same shape with all None values).
    v2_body_part = getattr(manifest, "body_part_examined", None)
    v2_manufacturer = getattr(manifest, "manufacturer", None)
    v2_model = getattr(manifest, "manufacturer_model_name", None)
    v2_sex = getattr(manifest, "patient_sex", None)
    v2_age_bucket_label = getattr(manifest, "patient_age_bucket", None)
    v2_age_bucket = _age_bucket_to_int(v2_age_bucket_label)
    v2_patient_age = getattr(manifest, "patient_age", None)
    v2_study_date = _parse_iso_date(getattr(manifest, "study_date_shifted", None))
    v2_thumbnail = getattr(manifest, "thumbnail", None)
    v2_series = list(getattr(manifest, "series", []) or [])
    # text-search-description Phase 1.5 (FR-TS15-6) — manifest v2.1 fields.
    # All Optional; absent on pre-Phase-1.5 manifest. Empty string is valid
    # ("scrubbed but all tokens stripped") and is preserved verbatim.
    v21_study_description = getattr(manifest, "study_description", None)
    v21_protocol_name = getattr(manifest, "protocol_name", None)
    v21_scrub_meta = getattr(manifest, "description_scrub_metadata", None) or {}
    v21_quarantine = bool(v21_scrub_meta.get("quarantine"))
    # Stable per-study patient pseudo key: hash(pseudo_study_uid). We don't
    # have a real cross-study pseudo_patient_id over the wire (v0.1.5 work),
    # so per-study keys are good enough to populate the patient_pseudo row
    # so facets can group on sex/age. Studies of the same patient will create
    # distinct rows for now — that's OK for facet count cardinality.
    v2_patient_key = (
        hashlib.sha256(manifest.pseudo_study_uid.encode("utf-8")).hexdigest()[:32]
        if (v2_sex is not None or v2_age_bucket is not None or v2_patient_age is not None)
        else None
    )

    # Optional thumbnail upload (FR-INGEST-2). MinIO PUT failures must NOT
    # fail the whole ingest — just log and skip the thumbnail (graceful
    # degradation NFR-AVAIL-1).
    preview_status: str | None = None
    preview_thumbnail_key: str | None = None
    if v2_thumbnail is not None:
        scrub = getattr(v2_thumbnail, "phi_scrub_status", "skipped_unknown")
        if scrub == "passed":
            try:
                jpeg_bytes = base64.b64decode(getattr(v2_thumbnail, "data_b64", "") or "")
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "thumbnail_b64_decode_fail",
                    extra={"event": "ingest.thumbnail.error", "error": str(exc)[:200]},
                )
                jpeg_bytes = b""
            if jpeg_bytes:
                thumb_key = f"thumbnails/{manifest.pseudo_study_uid}.jpg"
                try:
                    thumbnail_store = getattr(
                        request.app.state, "preview_object_store", None
                    )
                    target_store = thumbnail_store or store
                    target_store.put_object(
                        thumb_key, jpeg_bytes, content_type="image/jpeg"
                    )
                    preview_thumbnail_key = thumb_key
                    preview_status = "auto_verified"
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "thumbnail_put_fail",
                        extra={
                            "event": "ingest.thumbnail.error",
                            "error": str(exc)[:200],
                        },
                    )
        elif scrub == "skipped_burned_in":
            preview_status = "not_applicable"

    # DB commit.
    with session_factory() as session:
        hospital = get_hospital_by_pk(session, hospital_pk)
        assert hospital is not None
        # Build series entries — prefer v2 manifest series array when present,
        # otherwise fall back to the v1 single-series synthesis.
        series_entries: list[dict] = []
        if v2_series:
            # Distribute uploaded files across v2 series by index.
            file_iter = iter(range(len(manifest.files)))
            for s_idx, s in enumerate(v2_series):
                pseudo_series_uid = (
                    getattr(s, "pseudo_series_uid", None)
                    or f"{manifest.pseudo_study_uid}.{s_idx + 1}"
                )
                modality = getattr(s, "modality", None) or manifest.primary_modality()
                body_part = getattr(s, "body_part", None) or v2_body_part
                n_for_series = int(getattr(s, "n_instances", 0) or 0)
                instances = []
                for _ in range(n_for_series):
                    try:
                        i = next(file_iter)
                    except StopIteration:
                        break
                    instances.append(
                        {
                            "pseudo_sop_uid": (
                                manifest.pseudo_study_uid + f".{s_idx + 1}.{len(instances) + 1}"
                            ),
                            "sop_class_uid": None,
                            "instance_number": len(instances) + 1,
                            "object_key": uploaded_keys[i],
                            "bytes": manifest.files[i].bytes,
                            "sha256": bytes.fromhex(manifest.files[i].sha256),
                        }
                    )
                series_entries.append(
                    {
                        "pseudo_series_uid": pseudo_series_uid,
                        "modality": modality,
                        "body_part": body_part,
                        "series_number": s_idx + 1,
                        "instances": instances,
                        # text-search-description Phase 1.5 — per-series desc.
                        "series_description": getattr(s, "series_description", None),
                    }
                )
            # Any leftover files (manifest series counts misaligned) → trailing series.
            leftover = list(file_iter)
            if leftover:
                series_entries.append(
                    {
                        "pseudo_series_uid": (
                            manifest.pseudo_study_uid + f".{len(series_entries) + 1}"
                        ),
                        "modality": manifest.primary_modality(),
                        "body_part": v2_body_part,
                        "series_number": len(series_entries) + 1,
                        "instances": [
                            {
                                "pseudo_sop_uid": (
                                    manifest.pseudo_study_uid
                                    + f".{len(series_entries) + 1}.{n + 1}"
                                ),
                                "sop_class_uid": None,
                                "instance_number": n + 1,
                                "object_key": uploaded_keys[i],
                                "bytes": manifest.files[i].bytes,
                                "sha256": bytes.fromhex(manifest.files[i].sha256),
                            }
                            for n, i in enumerate(leftover)
                        ],
                    }
                )
        else:
            series_entries = [
                {
                    "pseudo_series_uid": manifest.pseudo_study_uid + ".1",
                    "modality": manifest.primary_modality(),
                    "body_part": v2_body_part,
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
            ]

        n_series = (
            int(getattr(manifest, "n_series", None) or len(series_entries) or 1)
        )
        # text-search-description Phase 1.5 (FR-TS15-10) — quarantine wins over
        # other preview_status values: a study with PHI-suspect description must
        # be hidden from buyer search regardless of thumbnail status.
        effective_preview_status = preview_status
        if v21_quarantine:
            effective_preview_status = "phi_detected"

        created_study = insert_study_full(
            session,
            hospital=hospital,
            pseudo_study_uid=manifest.pseudo_study_uid,
            gateway_id=manifest.gateway_id,
            central_job_id=central_job_id,
            n_instances=manifest.n_instances,
            n_series=n_series,
            total_bytes=manifest.total_bytes,
            modality=manifest.primary_modality(),
            body_part=v2_body_part,
            manufacturer=v2_manufacturer,
            model_name=v2_model,
            pseudo_patient_key=v2_patient_key,
            series_entries=series_entries,
            study_date_shifted=v2_study_date,
            patient_sex=v2_sex,
            patient_age_bucket=v2_age_bucket,
            patient_age=v2_patient_age,
            preview_status=effective_preview_status,
            preview_thumbnail_key=preview_thumbnail_key,
            raw_dicom_tags={
                "manifest_version": manifest.manifest_version,
                "deid_codes": list(manifest.deid.method_code_sequence),
                "thumbnail_phi_scrub_status": (
                    getattr(v2_thumbnail, "phi_scrub_status", None)
                    if v2_thumbnail is not None
                    else None
                ),
            },
            study_description=v21_study_description,
            protocol_name=v21_protocol_name,
            # buyer-search-v3 FR-V3-DATA-2 — propagate the gateway-extracted
            # KCD heuristic onto the study row so /v1/search/studies filters,
            # facets and sort can resolve diagnosis. Manifest field is
            # Optional (backward compat with pre-v3 ingests); when absent we
            # pass None and the column stays NULL.
            kcd_code=getattr(manifest, "kcd_code", None),
            kcd_label_ko=getattr(manifest, "kcd_label_ko", None),
            kcd_label_en=getattr(manifest, "kcd_label_en", None),
        )

        # FR-TS15-10 — record quarantine audit row when scrub flagged the study.
        if v21_quarantine:
            try:
                _record_quarantine(
                    session,
                    study_pk=created_study.study_pk,
                    scrub_meta=v21_scrub_meta,
                )
            except Exception as exc:  # noqa: BLE001
                # Audit failure must NOT block ingest; log + continue.
                log.warning(
                    "phi_quarantine_audit_insert_fail study_pk=%s err=%s",
                    created_study.study_pk,
                    str(exc)[:200],
                )

        # jpg-preview-defacing FR-PREVIEW-12 / FR-PREVIEW-13 / FR-AUDIT-1
        # (B-5 wiring). Persist the gateway-emitted manifest.preview block
        # into series.preview_*, dicom_preview_frame, phi_scrub_audit. All
        # writes share the same session/transaction as the study/series
        # INSERTs above so partial failure is impossible. Pre-jpg-preview-
        # defacing manifests carry preview=None and the helper is a no-op.
        manifest_preview = getattr(manifest, "preview", None)
        if manifest_preview is not None:
            _persist_preview_batch(
                session,
                pseudo_study_uid=manifest.pseudo_study_uid,
                manifest_preview=manifest_preview,
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
