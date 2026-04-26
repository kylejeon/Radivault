"""Backfill buyer-search-v3 fields onto already-ingested studies.

dev-spec-buyer-search-v3 FR-V3-OPS-1.

Walks every ``study`` row and:
  1. Recomputes KCD heuristic from (modality, body_part) →
     ``kcd_code`` / ``kcd_label_ko`` / ``kcd_label_en`` (default Z00.0).
  2. Re-derives exact ``patient_pseudo.age`` from ``raw_dicom_tags`` (or, when
     the original PatientAge tag was not preserved, synthesises a plausible
     integer from the existing ``age_bucket`` so demo rows are populated).
  3. Seeds ``hospital.region_pseudo`` for HOSP-001 / HOSP-002 (mirrors the
     alembic 0007 data migration so the script is idempotent on fresh DBs).

Usage::

    python -m scripts.demo_seed.backfill_v3_kcd_age_region [--dry-run] [--limit N]

Idempotent: re-running yields identical writes. ``--dry-run`` reports
intended changes without committing.

Performance: 250 study × ~100ms / row in a single PG transaction → < 30s.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from typing import Iterable

log = logging.getLogger("backfill.v3_kcd_age_region")

DEFAULT_DB_DSN = (
    "postgresql+psycopg://central_app:central_app@localhost:5432/central"
)

# HOSP-001 → SEOUL-A, HOSP-002 → BUSAN-B (matches alembic 0007 seed).
REGION_MAP = {
    "HOSP-001": "SEOUL-A",
    "HOSP-002": "BUSAN-B",
    # Future demo hospitals (no-op until enrolled).
    "HOSP-003": "DAEGU-C",
    "HOSP-004": "INCHEON-D",
}


def _make_session_factory(dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(dsn, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _bucket_to_synth_age(bucket: int | None, rng: random.Random) -> int | None:
    """Convert a 5-yr bucket lower bound (e.g. 50 → "50-54") into a plausible
    exact integer for demo rows when the original PatientAge tag is gone.

    Deterministic per-row via the supplied RNG (seeded by study_pk).
    """
    if bucket is None:
        return None
    lo = int(bucket)
    if lo >= 90:
        # Bucket "90+" — flatten to a uniform sample of 90-99.
        return rng.randint(90, 99)
    return rng.randint(lo, lo + 4)


def _exact_age_from_raw(raw: object | None, rng: random.Random) -> int | None:
    """Try to recover an exact age from ``study.raw_dicom_tags``.

    Returns ``None`` when no parseable signal exists. Inputs accepted:
    - dict with ``patient_age`` integer (post-v3 ingest)
    - dict with ``PatientAge`` string ("nnnY" / "nnnM")
    """
    if not isinstance(raw, dict):
        return None
    val = raw.get("patient_age")
    if isinstance(val, int) and 0 <= val <= 120:
        return val
    pa = raw.get("PatientAge") or raw.get("patient_age_raw")
    if isinstance(pa, str):
        from radivault_gateway.extract import _parse_age_exact

        return _parse_age_exact(pa)
    return None


def process_study(session, *, study, hospital_id_map: dict, rng: random.Random) -> dict:
    """Apply v3 backfill to one study row. Returns a dict of changes."""
    from radivault_central.db.models import Hospital, PatientPseudo
    from radivault_gateway.kcd_heuristic import lookup_kcd

    changes: dict = {"pseudo_study_uid": study.pseudo_study_uid}

    # 1) KCD heuristic.
    kcd = lookup_kcd(study.modality, study.body_part)
    if study.kcd_code != kcd.code:
        changes["kcd_code"] = (study.kcd_code, kcd.code)
        study.kcd_code = kcd.code
    if study.kcd_label_ko != kcd.label_ko:
        changes["kcd_label_ko"] = (study.kcd_label_ko, kcd.label_ko)
        study.kcd_label_ko = kcd.label_ko
    if study.kcd_label_en != kcd.label_en:
        changes["kcd_label_en"] = (study.kcd_label_en, kcd.label_en)
        study.kcd_label_en = kcd.label_en

    # 2) Exact patient_age.
    if study.patient_pseudo_pk is not None:
        pp = session.get(PatientPseudo, study.patient_pseudo_pk)
        if pp is not None and pp.age is None:
            new_age = _exact_age_from_raw(study.raw_dicom_tags, rng)
            if new_age is None:
                new_age = _bucket_to_synth_age(pp.age_bucket, rng)
            if new_age is not None:
                changes["patient_age"] = (None, new_age)
                pp.age = new_age

    # 3) hospital.region_pseudo (per-hospital lookup; cheap, idempotent).
    hosp = session.get(Hospital, study.hospital_pk)
    if hosp is not None:
        wanted = REGION_MAP.get(hosp.hospital_id)
        if wanted and hosp.region_pseudo != wanted:
            changes["hospital_region_pseudo"] = (hosp.region_pseudo, wanted)
            hosp.region_pseudo = wanted
            hospital_id_map[hosp.hospital_id] = wanted

    return changes


def run(*, dsn: str, limit: int | None, dry_run: bool, quiet: bool) -> int:
    from sqlalchemy import select

    from radivault_central.db.models import Study

    session_factory = _make_session_factory(dsn)
    n_total = 0
    n_changed = 0
    n_kcd_filled = 0
    n_age_filled = 0
    n_region_filled = 0
    hospital_id_map: dict[str, str] = {}

    with session_factory() as session:
        stmt = select(Study).order_by(Study.study_pk)
        if limit:
            stmt = stmt.limit(limit)
        for study in session.scalars(stmt):
            n_total += 1
            # Deterministic RNG per-study so re-runs yield identical synthetic
            # ages (idempotency).
            rng = random.Random(study.study_pk)
            changes = process_study(
                session, study=study, hospital_id_map=hospital_id_map, rng=rng
            )
            keys = [k for k in changes if k != "pseudo_study_uid"]
            if keys:
                n_changed += 1
                if "kcd_code" in changes:
                    n_kcd_filled += 1
                if "patient_age" in changes:
                    n_age_filled += 1
                if "hospital_region_pseudo" in changes:
                    n_region_filled += 1
                if not quiet:
                    log.info("study_changed %s: %s", study.pseudo_study_uid[:32], keys)

        if dry_run:
            session.rollback()
            log.info(
                "DRY-RUN total=%d changed=%d kcd=%d age=%d region=%d",
                n_total,
                n_changed,
                n_kcd_filled,
                n_age_filled,
                n_region_filled,
            )
        else:
            session.commit()
            log.info(
                "BACKFILL total=%d changed=%d kcd=%d age=%d region=%d hospitals=%s",
                n_total,
                n_changed,
                n_kcd_filled,
                n_age_filled,
                n_region_filled,
                hospital_id_map,
            )

    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-dsn", default=os.environ.get("CENTRAL_DSN", DEFAULT_DB_DSN))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info(
        "backfill_start dsn=%s limit=%s dry_run=%s",
        args.db_dsn.rsplit("@", 1)[-1] if "@" in args.db_dsn else args.db_dsn,
        args.limit,
        args.dry_run,
    )
    return run(
        dsn=args.db_dsn, limit=args.limit, dry_run=args.dry_run, quiet=args.quiet
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
