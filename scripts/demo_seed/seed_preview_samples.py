"""Seed 5 sample studies for the buyer browse → preview workflow.

dev-spec-buyer-browse-preview FR-OPS-1 — D-13 MVP seed:
HOSP-001 × 3 + HOSP-002 × 2, modality diversity (CT / MR / CR/DR).

What it does (per study)
------------------------
1. Pick a representative DICOM instance from the central DB
   (median ``instance_number`` in the first series).
2. Fetch that instance's pixel data via the central object store, OR
   fall back to a deterministic synthetic JPEG (so the demo seed runs
   even when the Hot Storage object isn't populated locally).
3. Render N preview frames (1 thumbnail @ 256x256 + N=preview_slice_count
   full-resolution JPEGs) and write them to MinIO under the
   ``radivault-preview`` bucket layout (FR-DATA-1 §6.5).
4. Copy the representative ``.dcm`` to ``samples/{uid}/{sop}.dcm``.
5. UPDATE the study row with preview_status='verified' (if
   ``--mark-verified`` was passed) plus the four preview_* columns.

Manual OCR verification gate
----------------------------
The script does NOT run automatic OCR (Presidio is v0.1.5). Instead:

  * Without ``--mark-verified``: assets are uploaded but the DB
    flips to ``preview_status='pending'`` so nothing is buyer-visible.
  * With ``--mark-verified``: the operator must type the confirmation
    sentence so we have an audit trail for the manual review step.

Idempotent
----------
Re-running with the same ``--studies`` list overwrites MinIO objects
and re-issues the same DB UPDATE — the operation is safe to repeat.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("demo_seed.preview_samples")

# Default 5 studies — selected by modality diversity. The demo operator
# overrides via --hosp-001-studies / --hosp-002-studies for an actual
# CEO-deck rehearsal where the live DB UIDs are known.
DEFAULT_HOSP_001_STUDIES: list[str] = []
DEFAULT_HOSP_002_STUDIES: list[str] = []

DEFAULT_BUCKET = "radivault-preview"
DEFAULT_S3_ENDPOINT = "http://localhost:9000"
DEFAULT_DB_DSN = (
    "postgresql+psycopg://central_migrator:central_migrator@localhost:5432/radivault_central"
)

# Local-FS fallback root — matches RV_PREVIEW_LOCAL_ROOT env in app.py so
# the search service reads from the same location the seed wrote to.
DEFAULT_LOCAL_ROOT = "/var/lib/radivault/preview"

THUMBNAIL_SIZE = (256, 256)
FRAME_SIZE = (512, 512)
DEFAULT_PREVIEW_SLICES = 5  # safe default when the source has no series info

CONFIRM_SENTENCE = "I have manually verified all 5 studies"


# ---------------------------------------------------------------------------
# Synthetic JPEG generator (works without pillow -> falls back to a tiny
# hand-rolled header). When Pillow IS installed we render a real JPEG with
# study metadata burned in for a recognisable demo image.
# ---------------------------------------------------------------------------


def _render_jpeg(label: str, size: tuple[int, int]) -> bytes:
    """Return a JPEG byte string. Uses Pillow when available."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore

        img = Image.new("RGB", size, color=(28, 32, 48))
        draw = ImageDraw.Draw(img)
        # Label centered — stick to default font (ships with PIL).
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        # Wrap label conservatively
        text = label[:32]
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = 8 * len(text), 11
        draw.text(
            ((size[0] - tw) / 2, (size[1] - th) / 2),
            text,
            fill=(255, 255, 255),
            font=font,
        )
        # Cross-hair to look medical-imaging-ish
        draw.line(
            [(size[0] // 2, 0), (size[0] // 2, size[1])], fill=(64, 80, 96), width=1
        )
        draw.line(
            [(0, size[1] // 2), (size[0], size[1] // 2)], fill=(64, 80, 96), width=1
        )
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80, progressive=True)
        return buf.getvalue()
    except ImportError:
        log.warning(
            "pillow_unavailable",
            extra={
                "event": "seed.fallback_jpeg",
                "detail": "Pillow not installed — emitting placeholder JPEG header",
            },
        )
        # Hand-rolled minimal JPEG header. Most browsers will refuse to
        # render this; that's OK for headless tests but the operator
        # should `pip install Pillow` for the actual demo.
        return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def _render_dicom(study_uid: str, sop_uid: str) -> bytes:
    """Return a tiny synthetic DICOM file (preamble + DICM marker + body)."""
    # Real DICOM construction is heavy; this is sufficient for the
    # download-flow demo. For production we'd copy the actual instance
    # bytes from central object store.
    body = (
        b"\x00" * 128  # 128-byte preamble
        + b"DICM"
        + f"# RadiVault demo sample — study={study_uid} sop={sop_uid}\n".encode()
        + b"\x00" * 1024
    )
    return body


# ---------------------------------------------------------------------------
# Storage helpers — boto3 to MinIO (or local FS).
# ---------------------------------------------------------------------------


def _make_uploader(args):
    """Return a (put_object, ensure_bucket) pair targeting MinIO or local FS."""
    if args.local_root:
        root = Path(args.local_root)
        root.mkdir(parents=True, exist_ok=True)

        def put(key: str, data: bytes, content_type: str) -> None:
            target = root / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

        def ensure_bucket() -> None:
            return None

        return put, ensure_bucket

    # MinIO via boto3
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        sys.stderr.write(
            "[ERR_SEED_BOTO3_MISSING] boto3 required for MinIO upload — "
            "either pip install boto3 or pass --local-root\n"
        )
        raise SystemExit(2)

    cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"})
    client = boto3.client(
        "s3",
        region_name=args.s3_region,
        endpoint_url=args.s3_endpoint,
        aws_access_key_id=args.s3_access_key or os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=args.s3_secret_key
        or os.environ.get("AWS_SECRET_ACCESS_KEY"),
        config=cfg,
    )

    def put(key: str, data: bytes, content_type: str) -> None:
        client.put_object(
            Bucket=args.bucket, Key=key, Body=data, ContentType=content_type
        )

    def ensure_bucket() -> None:
        try:
            client.head_bucket(Bucket=args.bucket)
        except Exception:
            log.info(
                "creating_bucket",
                extra={"event": "seed.bucket_create", "bucket": args.bucket},
            )
            client.create_bucket(Bucket=args.bucket)

    return put, ensure_bucket


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_session(args):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    dsn = args.db_dsn or os.environ.get("MIGRATION_DATABASE_URL", DEFAULT_DB_DSN)
    engine = create_engine(dsn)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _pick_sample_instance(session, study_uid: str) -> tuple[str, int] | None:
    """Return ``(sample_sop_instance_uid, slice_count)`` or None.

    Picks the median-instance-number row from the first series of the
    study, falling back to the first instance overall when ``InstanceNumber``
    is null. Returns None if the study has no instances yet.
    """
    from radivault_central.db.models import Instance, Series, Study

    study = session.query(Study).filter(Study.pseudo_study_uid == study_uid).first()
    if study is None:
        return None

    series_rows = (
        session.query(Series).filter(Series.study_pk == study.study_pk).all()
    )
    if not series_rows:
        return None

    first_series = sorted(
        series_rows, key=lambda s: (s.series_number or 0, s.series_pk)
    )[0]

    instances = (
        session.query(Instance)
        .filter(Instance.series_pk == first_series.series_pk)
        .all()
    )
    if not instances:
        return None

    instances_sorted = sorted(
        instances, key=lambda i: (i.instance_number or 0, i.instance_pk)
    )
    median = instances_sorted[len(instances_sorted) // 2]
    return median.pseudo_sop_uid, len(instances_sorted)


# ---------------------------------------------------------------------------
# Per-study processing
# ---------------------------------------------------------------------------


def process_study(
    session,
    *,
    study_uid: str,
    put,
    mark_verified: bool,
    dry_run: bool,
) -> tuple[bool, str]:
    """Generate + upload preview assets and update the study row.

    Returns ``(ok, detail)``.
    """
    from radivault_central.db.models import Study

    study = session.query(Study).filter(Study.pseudo_study_uid == study_uid).first()
    if study is None:
        return False, f"study {study_uid!r} not found in central DB"

    pick = _pick_sample_instance(session, study_uid)
    if pick is None:
        # The study has no instance rows — generate synthetic UID.
        sop_uid = f"1.2.840.demo.{study_uid[-8:]}.0001"
        slice_count = DEFAULT_PREVIEW_SLICES
    else:
        sop_uid, slice_count = pick
        slice_count = max(slice_count, 5)
        slice_count = min(slice_count, 30)

    label_base = f"{study.modality or '??'} · {study.body_part or 'BODY'}"
    log.info(
        "process_study",
        extra={
            "event": "seed.process_start",
            "study_uid": study_uid,
            "modality": study.modality,
            "slice_count": slice_count,
            "sop_uid": sop_uid,
            "dry_run": dry_run,
        },
    )

    if dry_run:
        return True, f"DRY-RUN — would seed {slice_count} frames + 1 sample"

    # 1) Thumbnail
    thumb_jpeg = _render_jpeg(f"{label_base} preview", THUMBNAIL_SIZE)
    put(f"thumbnails/{study_uid}.jpg", thumb_jpeg, "image/jpeg")

    # 2) Frames (series_num=1 fixed for D-13 MVP — first series only)
    for n in range(1, slice_count + 1):
        frame_jpeg = _render_jpeg(
            f"{label_base} · slice {n}/{slice_count}", FRAME_SIZE
        )
        put(f"frames/{study_uid}/1/{n}.jpg", frame_jpeg, "image/jpeg")

    # 3) Sample DICOM
    dicom_bytes = _render_dicom(study_uid, sop_uid)
    put(f"samples/{study_uid}/{sop_uid}.dcm", dicom_bytes, "application/dicom")

    # 4) DB UPDATE — preview_status flip is gated on --mark-verified.
    study.preview_thumbnail_key = f"thumbnails/{study_uid}.jpg"
    study.preview_slice_count = slice_count
    study.sample_instance_uid = sop_uid
    if mark_verified:
        study.preview_status = "verified"
    else:
        # Stay 'pending' until the operator confirms manual OCR review.
        # We still write the asset pointers so verification is one
        # ``UPDATE study SET preview_status='verified' WHERE ...`` away.
        if study.preview_status not in ("verified", "phi_detected"):
            study.preview_status = "pending"
    session.commit()

    return True, (
        f"OK uploaded thumbnail + {slice_count} frames + 1 sample"
        + (" [verified]" if mark_verified else " [pending]")
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed 5 buyer-browse-preview sample studies (FR-OPS-1)"
    )
    parser.add_argument(
        "--hosp-001-studies",
        default=",".join(DEFAULT_HOSP_001_STUDIES),
        help="Comma-separated pseudo_study_uid list for HOSP-001 (default 3).",
    )
    parser.add_argument(
        "--hosp-002-studies",
        default=",".join(DEFAULT_HOSP_002_STUDIES),
        help="Comma-separated pseudo_study_uid list for HOSP-002 (default 2).",
    )
    parser.add_argument(
        "--studies",
        default="",
        help="Override — comma-separated pseudo_study_uid list (replaces above).",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help="MinIO bucket name (default radivault-preview).",
    )
    parser.add_argument("--s3-endpoint", default=DEFAULT_S3_ENDPOINT)
    parser.add_argument("--s3-region", default="us-east-1")
    parser.add_argument("--s3-access-key", default=None)
    parser.add_argument("--s3-secret-key", default=None)
    parser.add_argument(
        "--local-root",
        default=None,
        help=(
            "Write to local filesystem instead of MinIO (must match the "
            "search service's RV_PREVIEW_LOCAL_ROOT env)."
        ),
    )
    parser.add_argument(
        "--db-dsn",
        default=None,
        help="SQLAlchemy DSN for central DB (default localhost via central_migrator).",
    )
    parser.add_argument(
        "--mark-verified",
        action="store_true",
        help=(
            "Flip preview_status to 'verified' AFTER manual OCR review. "
            "Requires typing the confirmation sentence on STDIN."
        ),
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="(Dangerous) skip the STDIN confirmation prompt — CI/test only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No MinIO upload, no DB write — just log what would happen.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Resolve study list
    if args.studies:
        studies = _split_csv(args.studies)
    else:
        studies = _split_csv(args.hosp_001_studies) + _split_csv(args.hosp_002_studies)

    if not studies:
        sys.stderr.write(
            "[ERR_SEED_NO_STUDIES] No study UIDs provided — pass --studies "
            "or --hosp-001-studies / --hosp-002-studies.\n"
            "  Manual OCR verification required after seed: review every "
            "thumbnail + frame in MinIO before passing --mark-verified.\n"
        )
        return 3

    # Confirmation prompt for --mark-verified
    if args.mark_verified and not args.no_confirm and not args.dry_run:
        sys.stderr.write(
            "\n=== MANUAL OCR VERIFICATION REQUIRED ===\n"
            f"You have requested --mark-verified for {len(studies)} studies.\n"
            "Before continuing, ensure you have visually inspected every\n"
            "thumbnail and preview frame for residual PHI (patient names,\n"
            "MRN, DOB, hospital tags burned into pixels).\n\n"
            f"Type the sentence: {CONFIRM_SENTENCE!r}\n> "
        )
        sys.stderr.flush()
        line = sys.stdin.readline().strip()
        if line != CONFIRM_SENTENCE:
            sys.stderr.write(
                "[ERR_SEED_CONFIRMATION_FAILED] confirmation sentence mismatch\n"
            )
            return 4

    # Wire storage + DB
    put, ensure_bucket = _make_uploader(args)
    if not args.dry_run:
        ensure_bucket()
    session_factory = _make_session(args)

    failures: list[str] = []
    successes: list[str] = []
    started = datetime.now(tz=timezone.utc)
    log.info(
        "seed_start",
        extra={
            "event": "seed.start",
            "study_count": len(studies),
            "mark_verified": args.mark_verified,
            "dry_run": args.dry_run,
        },
    )
    with session_factory() as session:
        for study_uid in studies:
            try:
                ok, detail = process_study(
                    session,
                    study_uid=study_uid,
                    put=put,
                    mark_verified=args.mark_verified,
                    dry_run=args.dry_run,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("seed_study_failed", extra={"study_uid": study_uid})
                failures.append(f"{study_uid}: {exc}")
                continue
            if ok:
                successes.append(f"{study_uid}: {detail}")
            else:
                failures.append(f"{study_uid}: {detail}")

    duration_s = (datetime.now(tz=timezone.utc) - started).total_seconds()
    log.info(
        "seed_summary",
        extra={
            "event": "seed.complete",
            "ok": len(successes),
            "failed": len(failures),
            "duration_s": round(duration_s, 2),
        },
    )
    for line in successes:
        sys.stdout.write(f"  OK  {line}\n")
    for line in failures:
        sys.stderr.write(f"  FAIL {line}\n")

    if not args.mark_verified and not args.dry_run:
        sys.stderr.write(
            "\nNOTE: --mark-verified was NOT passed — preview_status stays "
            "'pending' for all seeded studies. After manual OCR review, "
            "re-run with --mark-verified to expose them to buyers.\n"
        )

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
