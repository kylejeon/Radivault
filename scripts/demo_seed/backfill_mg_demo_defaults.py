"""Seed synthetic Sex / Age / Manufacturer / Model defaults onto MG studies.

D-13 demo unblocker (Track 2 Option A — Kyle decision 2026-04-26).

TCIA CBIS-DDSM source DICOMs leave PatientSex/PatientAge/Manufacturer/
ManufacturerModelName tags blank, so the gateway extract path correctly writes
NULL into the central DB. For demo narrative we backfill clinically plausible
defaults that match real mammography practice:

- 99%+ of screening MG patients are female → ``sex = 'F'``.
- Korean national screening age 40-70 → uniform integer in [40, 70].
- Manufacturer mix mirrors CBIS-DDSM scanner inventory:
  * 50% Hologic / Selenia Dimensions
  * 30% GE Medical Systems / Senographe Pristina
  * 20% Siemens Healthineers / Mammomat Inspiration

Distribution is deterministic (SHA-256 of pseudo_study_uid) so re-runs assign
identical values. Idempotent: rows with non-NULL ``manufacturer`` are skipped.

Usage::

    python -m scripts.demo_seed.backfill_mg_demo_defaults [--dry-run] [-v]
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from typing import Iterable

log = logging.getLogger("backfill.mg_demo_defaults")

DEFAULT_DB_DSN = "postgresql+psycopg://central_app:central_app@localhost:5432/central"

# (cumulative_threshold_/100, manufacturer, model_name)
SCANNER_MIX = (
    (50, "Hologic", "Selenia Dimensions"),
    (80, "GE Medical Systems", "Senographe Pristina"),
    (100, "Siemens Healthineers", "Mammomat Inspiration"),
)
DISCLAIMER = "synthetic — TCIA CBIS-DDSM source lacks Sex/Age/Manufacturer tags"
SEED_TAG_KEY = "mg_demo_defaults_seeded_by"
SEED_TAG_VALUE = "backfill_mg_demo_defaults.py"
DISCLAIMER_KEY = "mg_demo_defaults_disclaimer"


def _make_session_factory(dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=create_engine(dsn, pool_pre_ping=True), expire_on_commit=False)


def _hash_int(uid: str, salt: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{salt}:{uid}".encode("utf-8")).digest()[:8], "big")


def _pick_scanner(uid: str) -> tuple[str, str]:
    bucket = _hash_int(uid, "scanner") % 100
    for threshold, mfg, model in SCANNER_MIX:
        if bucket < threshold:
            return mfg, model
    return SCANNER_MIX[-1][1], SCANNER_MIX[-1][2]


def _pick_age(uid: str) -> int:
    return 40 + (_hash_int(uid, "age") % 31)  # uniform [40, 70]


def _age_bucket_lo(age: int) -> int:
    return (age // 5) * 5


def _pseudo_patient_key(uid: str) -> str:
    return f"mg_demo_{hashlib.sha256(uid.encode('utf-8')).hexdigest()[:16]}"


def process_study(session, *, study) -> dict:
    """Apply MG demo defaults to one study row. Returns dict of changes."""
    from sqlalchemy import select

    from radivault_central.db.models import PatientPseudo

    if study.manufacturer is not None:
        return {}  # idempotency guard

    changes: dict = {}
    mfg, model = _pick_scanner(study.pseudo_study_uid)
    study.manufacturer = mfg
    study.model_name = model
    changes["manufacturer"] = mfg
    changes["model_name"] = model

    if study.patient_pseudo_pk is None:
        age = _pick_age(study.pseudo_study_uid)
        bucket_lo = _age_bucket_lo(age)
        ppk = _pseudo_patient_key(study.pseudo_study_uid)
        pp = session.scalar(
            select(PatientPseudo).where(
                PatientPseudo.hospital_pk == study.hospital_pk,
                PatientPseudo.pseudo_patient_key == ppk,
            )
        )
        if pp is None:
            pp = PatientPseudo(
                hospital_pk=study.hospital_pk,
                pseudo_patient_key=ppk,
                sex="F",
                age=age,
                age_bucket=bucket_lo,
            )
            session.add(pp)
            session.flush()
        else:
            if pp.sex is None:
                pp.sex = "F"
            if pp.age is None:
                pp.age = age
            if pp.age_bucket is None:
                pp.age_bucket = bucket_lo
        study.patient_pseudo_pk = pp.patient_pseudo_pk
        changes.update(sex="F", age=age, age_bucket=f"{bucket_lo}-{bucket_lo + 4}",
                       patient_pseudo_pk=pp.patient_pseudo_pk)

    raw = dict(study.raw_dicom_tags) if isinstance(study.raw_dicom_tags, dict) else {}
    raw[SEED_TAG_KEY] = SEED_TAG_VALUE
    raw[DISCLAIMER_KEY] = DISCLAIMER
    study.raw_dicom_tags = raw
    return changes


def run(*, dsn: str, dry_run: bool, verbose: bool) -> int:
    from sqlalchemy import select, text

    from radivault_central.db.models import Study

    session_factory = _make_session_factory(dsn)
    n_total = n_seeded = n_skipped = 0

    with session_factory() as session:
        stmt = select(Study).where(Study.modality == "MG").order_by(Study.study_pk)
        for study in session.scalars(stmt):
            n_total += 1
            changes = process_study(session, study=study)
            if not changes:
                n_skipped += 1
                if verbose:
                    log.debug("skip %s", study.pseudo_study_uid[:32])
                continue
            n_seeded += 1
            if verbose:
                log.info("seed %s %s", study.pseudo_study_uid[:32], list(changes))

        if dry_run:
            session.rollback()
            log.info("DRY-RUN total=%d would_seed=%d skipped=%d", n_total, n_seeded, n_skipped)
        else:
            session.commit()
            log.info("BACKFILL total=%d seeded=%d skipped=%d", n_total, n_seeded, n_skipped)

        verify_sql = text(
            """
            SELECT s.modality, COUNT(*) AS total,
                   SUM(CASE WHEN s.manufacturer IS NULL THEN 1 ELSE 0 END) AS no_mfg,
                   SUM(CASE WHEN s.model_name IS NULL THEN 1 ELSE 0 END) AS no_model,
                   SUM(CASE WHEN p.age IS NULL THEN 1 ELSE 0 END) AS no_age,
                   SUM(CASE WHEN p.sex IS NULL THEN 1 ELSE 0 END) AS no_sex
              FROM study s
              LEFT JOIN patient_pseudo p ON p.patient_pseudo_pk = s.patient_pseudo_pk
             WHERE s.modality = 'MG' GROUP BY s.modality
            """
        )
        row = session.execute(verify_sql).fetchone()
        if row is None:
            log.warning("VERIFY no MG rows found")
        else:
            log.info(
                "VERIFY modality=%s total=%d no_mfg=%d no_model=%d no_age=%d no_sex=%d",
                row.modality, row.total, row.no_mfg, row.no_model, row.no_age, row.no_sex,
            )
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-dsn", default=os.environ.get("CENTRAL_DSN", DEFAULT_DB_DSN))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info(
        "mg_demo_seed_start dsn=%s dry_run=%s",
        args.db_dsn.rsplit("@", 1)[-1] if "@" in args.db_dsn else args.db_dsn,
        args.dry_run,
    )
    return run(dsn=args.db_dsn, dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
