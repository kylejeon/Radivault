"""Backfill metadata-thumbnail-ingest v2 fields for already-ingested studies.

dev-spec-metadata-thumbnail-ingest FR-BACKFILL-1: D-13 demo unblocker.

The first-pass ingest path wrote ``study.body_part`` / ``manufacturer`` /
``model_name`` / ``study_date_shifted`` as NULL because the v1 manifest never
carried those fields. This script re-derives them from the source PACS
(Orthanc) and applies them to the central DB *in place*, plus uploads a
256x256 JPEG thumbnail to MinIO under
``radivault-preview/thumbnails/{pseudo_study_uid}.jpg``.

Inputs:
- Orthanc HTTP API for the original DICOM bytes.
- Gateway ``state.sqlite3`` ``uid_map`` table for original_uid →
  pseudo_uid resolution (no re-derivation needed — we trust whatever the
  Gateway already wrote on the first ingest).
- Central Postgres for the UPDATE.
- MinIO for the thumbnail PUT.

Idempotent: re-running on the same pseudo_study_uid simply overwrites the
DB row + MinIO object. ``preview_status`` is never downgraded from
``verified`` / ``phi_detected`` (manual review wins).

Performance: single-process, sequential. Expected ~3–4s/study × 250 ≈ 15min
on the demo workstation. Add ``--workers N`` later if needed.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

log = logging.getLogger("backfill.v2_metadata")

DEFAULT_ORTHANC = "http://localhost:8042"
DEFAULT_ORTHANC_USER = "orthanc"
DEFAULT_ORTHANC_PASS = "orthanc"
DEFAULT_DB_DSN = (
    "postgresql+psycopg://central_app:central_app@localhost:5432/central"
)
DEFAULT_STATE_DB = "/Users/yonghyuk/Radivault/demo_data/gateway/state.sqlite3"
DEFAULT_S3_ENDPOINT = "http://localhost:9000"
DEFAULT_S3_KEY = "minioadmin"
DEFAULT_S3_SECRET = "minioadmin"
DEFAULT_BUCKET = "radivault-preview"


def _build_minio_client(args):
    import boto3
    from botocore.config import Config

    cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"})
    return boto3.client(
        "s3",
        region_name="us-east-1",
        endpoint_url=args.s3_endpoint,
        aws_access_key_id=args.s3_access_key,
        aws_secret_access_key=args.s3_secret_key,
        config=cfg,
    )


def _ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)


def _orthanc_get_json(args, path: str) -> object:
    import requests

    r = requests.get(
        f"{args.orthanc}{path}",
        auth=(args.orthanc_user, args.orthanc_password),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _orthanc_get_bytes(args, path: str) -> bytes:
    import requests

    r = requests.get(
        f"{args.orthanc}{path}",
        auth=(args.orthanc_user, args.orthanc_password),
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def _list_orthanc_studies(args) -> list[str]:
    """Return Orthanc-internal study IDs."""
    return _orthanc_get_json(args, "/studies")


def _study_metadata(args, orthanc_study_id: str) -> dict:
    return _orthanc_get_json(args, f"/studies/{orthanc_study_id}")


def _instances_for_study(args, orthanc_study_id: str) -> list[str]:
    """Return Orthanc-internal instance IDs for a given study."""
    raw = _orthanc_get_json(args, f"/studies/{orthanc_study_id}/instances")
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and item.get("ID"):
            out.append(str(item["ID"]))
    # Sort by InstanceNumber so the middle-slice picker is deterministic.
    if raw and isinstance(raw[0], dict):
        try:
            paired = []
            for item in raw:
                if not isinstance(item, dict) or not item.get("ID"):
                    continue
                in_no = (
                    int(item.get("MainDicomTags", {}).get("InstanceNumber", 0) or 0)
                    if item.get("MainDicomTags")
                    else 0
                )
                paired.append((in_no, str(item["ID"])))
            paired.sort()
            out = [pid for _, pid in paired]
        except Exception:
            pass
    return out


def _instance_dicom(args, orthanc_instance_id: str, target: Path) -> Path:
    data = _orthanc_get_bytes(args, f"/instances/{orthanc_instance_id}/file")
    target.write_bytes(data)
    return target


def _connect_state_db(path: str) -> sqlite3.Connection:
    if not Path(path).exists():
        raise FileNotFoundError(f"gateway state DB not found at {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_pseudo_study_uid(state_conn: sqlite3.Connection, original_uid: str) -> str | None:
    row = state_conn.execute(
        "SELECT pseudo_uid FROM uid_map WHERE original_uid = ? AND uid_kind = 'study'",
        (original_uid,),
    ).fetchone()
    return row["pseudo_uid"] if row else None


def _make_session(dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(dsn)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _bucket_label_to_int(label: str | None) -> int | None:
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


def process_one(
    args,
    *,
    state_conn,
    session_factory,
    s3_client,
    orthanc_study_id: str,
    tmp_root: Path,
) -> tuple[bool, str]:
    """Pull, extract, upload, UPDATE for a single Orthanc study."""
    import hashlib

    from radivault_central.db.models import PatientPseudo, Study
    from radivault_gateway.extract import extract_study_metadata
    from radivault_gateway.thumbnail import generate_thumbnail

    meta = _study_metadata(args, orthanc_study_id)
    main_tags = meta.get("MainDicomTags", {}) or {}
    original_uid = main_tags.get("StudyInstanceUID") or ""
    if not original_uid:
        return False, f"orthanc study {orthanc_study_id} missing StudyInstanceUID"

    pseudo_uid = _resolve_pseudo_study_uid(state_conn, original_uid)
    if not pseudo_uid:
        return False, f"no uid_map entry for {original_uid}"

    instance_ids = _instances_for_study(args, orthanc_study_id)
    if not instance_ids:
        return False, f"no instances for {pseudo_uid}"

    # Pull a representative subset (middle 5 if many) to keep extract fast
    # but still let the thumbnail pick a true mid-slice.
    subset = instance_ids
    if len(subset) > 30:
        # Keep a contiguous middle window — InstanceNumber order matches
        # Orthanc's natural list order in practice.
        mid = len(subset) // 2
        subset = subset[max(0, mid - 15) : mid + 15]

    study_tmp = tmp_root / orthanc_study_id
    study_tmp.mkdir(parents=True, exist_ok=True)
    paths = []
    for inst_id in subset:
        target = study_tmp / f"{inst_id}.dcm"
        try:
            paths.append(_instance_dicom(args, inst_id, target))
        except Exception as exc:  # noqa: BLE001
            log.warning("orthanc fetch fail %s: %s", inst_id, exc)
            continue
    if not paths:
        return False, f"no instances downloaded for {pseudo_uid}"

    md = extract_study_metadata(paths)
    primary_modality = md.series[0]["modality"] if md.series else None
    thumb = generate_thumbnail(
        paths, modality=primary_modality, body_part=md.body_part_examined
    )

    preview_thumb_key = None
    preview_status = None
    if thumb is not None:
        preview_thumb_key = f"thumbnails/{pseudo_uid}.jpg"
        s3_client.put_object(
            Bucket=args.bucket,
            Key=preview_thumb_key,
            Body=thumb.bytes,
            ContentType="image/jpeg",
        )
        preview_status = "auto_verified"

    # UPDATE central row.
    age_int = _bucket_label_to_int(md.patient_age_bucket)
    patient_key = (
        hashlib.sha256(pseudo_uid.encode("utf-8")).hexdigest()[:32]
        if (md.patient_sex is not None or age_int is not None)
        else None
    )
    with session_factory() as session:
        from sqlalchemy import select

        study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo_uid))
        if study is None:
            shutil_rmtree(study_tmp)
            return False, f"central row missing for {pseudo_uid}"
        if md.body_part_examined is not None:
            study.body_part = md.body_part_examined
        if md.manufacturer is not None:
            study.manufacturer = md.manufacturer
        if md.manufacturer_model_name is not None:
            study.model_name = md.manufacturer_model_name
        if md.study_date_shifted is not None:
            study.study_date_shifted = md.study_date_shifted
        if preview_thumb_key is not None:
            study.preview_thumbnail_key = preview_thumb_key
        if preview_status is not None and study.preview_status not in (
            "verified",
            "phi_detected",
        ):
            study.preview_status = preview_status
        # raw_dicom_tags audit trail (FR-INGEST-1).
        study.raw_dicom_tags = {
            "manifest_version": 2,
            "deid_codes": ["113100", "113101", "113103", "113106", "113109", "113111"],
            "thumbnail_phi_scrub_status": (
                thumb.phi_scrub_status if thumb is not None else "skipped_unknown"
            ),
            "backfilled_by": "backfill_v2_metadata.py",
        }

        # patient_pseudo upsert for sex/age facets.
        if patient_key:
            pp = session.scalar(
                select(PatientPseudo).where(
                    PatientPseudo.hospital_pk == study.hospital_pk,
                    PatientPseudo.pseudo_patient_key == patient_key,
                )
            )
            if pp is None:
                pp = PatientPseudo(
                    hospital_pk=study.hospital_pk,
                    pseudo_patient_key=patient_key,
                    sex=md.patient_sex,
                    age_bucket=age_int,
                )
                session.add(pp)
                session.flush()
            else:
                if md.patient_sex is not None and pp.sex is None:
                    pp.sex = md.patient_sex
                if age_int is not None and pp.age_bucket is None:
                    pp.age_bucket = age_int
            study.patient_pseudo_pk = pp.patient_pseudo_pk
        session.commit()

    shutil_rmtree(study_tmp)
    return True, (
        f"OK pseudo={pseudo_uid[:30]} body={md.body_part_examined} "
        f"mfg={md.manufacturer} model={md.manufacturer_model_name} sex={md.patient_sex} "
        f"age={md.patient_age_bucket} date={md.study_date_shifted} thumb={'Y' if thumb else 'N'}"
    )


def shutil_rmtree(p: Path) -> None:
    import shutil

    try:
        shutil.rmtree(p)
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill v2 metadata + thumbnail")
    parser.add_argument("--orthanc", default=DEFAULT_ORTHANC)
    parser.add_argument("--orthanc-user", default=DEFAULT_ORTHANC_USER)
    parser.add_argument("--orthanc-password", default=DEFAULT_ORTHANC_PASS)
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--state-db", default=DEFAULT_STATE_DB)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--s3-endpoint", default=DEFAULT_S3_ENDPOINT)
    parser.add_argument("--s3-access-key", default=DEFAULT_S3_KEY)
    parser.add_argument("--s3-secret-key", default=DEFAULT_S3_SECRET)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info("backfill_start state_db=%s orthanc=%s bucket=%s",
             args.state_db, args.orthanc, args.bucket)

    state_conn = _connect_state_db(args.state_db)
    session_factory = _make_session(args.db_dsn)
    s3 = _build_minio_client(args)
    _ensure_bucket(s3, args.bucket)

    try:
        studies = _list_orthanc_studies(args)
    except Exception as exc:
        log.error("orthanc list failed: %s", exc)
        return 2

    if args.limit:
        studies = studies[: args.limit]
    log.info("backfill_targets count=%d", len(studies))

    import tempfile

    successes = 0
    failures = 0
    fail_reasons: dict[str, int] = {}
    started = time.time()

    with tempfile.TemporaryDirectory(prefix="radivault_backfill_") as tmpdir:
        tmp_root = Path(tmpdir)
        for i, oid in enumerate(studies, 1):
            if args.dry_run:
                meta = _study_metadata(args, oid)
                log.info(
                    "[%d/%d] DRY %s tags=%s", i, len(studies), oid,
                    meta.get("MainDicomTags", {}).get("StudyInstanceUID"),
                )
                continue
            try:
                ok, detail = process_one(
                    args,
                    state_conn=state_conn,
                    session_factory=session_factory,
                    s3_client=s3,
                    orthanc_study_id=oid,
                    tmp_root=tmp_root,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("study failed %s", oid)
                ok, detail = False, f"exception: {exc}"
            if ok:
                successes += 1
                log.info("[%d/%d] %s", i, len(studies), detail)
            else:
                failures += 1
                key = detail.split(":", 1)[0][:32]
                fail_reasons[key] = fail_reasons.get(key, 0) + 1
                log.warning("[%d/%d] FAIL %s", i, len(studies), detail)

    duration = time.time() - started
    log.info(
        "backfill_summary ok=%d fail=%d duration_s=%.1f",
        successes,
        failures,
        duration,
    )
    if fail_reasons:
        log.info("backfill_fail_reasons %s", fail_reasons)
    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
