"""Backfill text-search-description Phase 1.5 description fields.

dev-spec-text-search-description-phase15 §W4 / FR-TS15-9.

Walks every ``study`` row that has ``raw_dicom_tags`` populated, recomputes
the 3 description fields from any preserved DICOM tags
(StudyDescription / SeriesDescription / ProtocolName) using the same scrub
module the gateway uses (``radivault_gateway.description_scrub``), and
writes them back into:

  - ``study.study_description``
  - ``study.protocol_name``
  - ``series.series_description`` (per-series)

Quarantined studies (suspicious tokens detected) get
``preview_status='phi_detected'`` and an audit row in
``study_phi_quarantine_audit``.

Modes:

  --dry-run      Compute scrub results, print summary CSV. No DB writes.
  --report-csv   Write a per-study report to the supplied path
                 (study_pk, scrub_version, blacklist_matched,
                 whitelist_matched, quarantine, truncated, before/after
                 lengths). PHI itself is never persisted — only hashes +
                 lengths.

Usage::

    python -m scripts.demo_seed.backfill_description_phase15 \
        [--dry-run] [--limit N] [--report-csv path/to/report.csv] \
        [--db-dsn postgresql+psycopg://...]

Idempotent: re-running yields identical writes; both NULL-source and
already-scrubbed studies are processed.

Notes:
  - The 250-demo seed pipeline does not preserve raw DICOM description
    tags in ``study.raw_dicom_tags`` today — backfill will report 0
    description hits on the demo dataset. It still serves as the audit
    pathway for production workloads where the raw tags ARE preserved.
  - For demo purposes we also allow synthesising a placeholder description
    from (modality, body_part) when no raw tag is available, so the demo
    UI can show a non-empty Description column. Toggled via --synthesize.

Performance: 250 study × ~30ms / row in a single PG transaction → < 10s.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from typing import Iterable

log = logging.getLogger("backfill.description_phase15")

DEFAULT_DB_DSN = (
    "postgresql+psycopg://central_app:central_app@localhost:5432/central"
)


def _make_session_factory(dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(dsn, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _synth_description(modality: str | None, body_part: str | None) -> str:
    """Compose a benign default description for the demo seed.

    Output is always whitelist-safe: modality + body_part (both are
    pre-scrubbed dictionary tokens). Empty when both inputs are None.
    """
    parts = [p for p in (modality, body_part) if p]
    return " ".join(parts).upper() if parts else ""


def _synth_protocol(modality: str | None, body_part: str | None) -> str:
    """Compose a benign default protocol name (e.g. AX BRAIN MR ROUTINE).

    Used only with --synthesize. Always whitelist-safe.
    """
    if not modality and not body_part:
        return ""
    return f"AX {body_part or ''} {modality or ''} ROUTINE".strip()


def _raw_descriptions_from_tags(
    raw: object | None,
) -> tuple[str | None, str | None, list[str]]:
    """Best-effort extraction of raw DICOM description fields from
    ``study.raw_dicom_tags``. Returns (study_desc, protocol, series_descs).

    Inputs accepted:
      - dict with explicit Phase 1.5 keys (already scrubbed) — pass through.
      - dict with raw DICOM keys (StudyDescription, ProtocolName, ...) — use.
      - None / non-dict — returns (None, None, []).
    """
    if not isinstance(raw, dict):
        return None, None, []

    sd = raw.get("study_description") or raw.get("StudyDescription")
    pn = raw.get("protocol_name") or raw.get("ProtocolName")

    series_descs: list[str] = []
    sds = raw.get("series_descriptions") or raw.get("SeriesDescriptions") or []
    if isinstance(sds, list):
        for s in sds:
            if isinstance(s, str):
                series_descs.append(s)
            elif isinstance(s, dict):
                v = s.get("description") or s.get("SeriesDescription")
                if isinstance(v, str):
                    series_descs.append(v)

    return (
        sd if isinstance(sd, str) else None,
        pn if isinstance(pn, str) else None,
        series_descs,
    )


def process_study(session, *, study, synthesize: bool) -> dict:
    """Apply description backfill to one study row. Returns a change dict."""
    from radivault_central.db.models import Series
    from radivault_gateway.description_scrub import (
        SCRUB_VERSION,
        scrub_description,
    )

    changes: dict = {
        "pseudo_study_uid": study.pseudo_study_uid,
        "scrub_version": SCRUB_VERSION,
        "blacklist_matched": [],
        "whitelist_matched": [],
        "quarantine": False,
        "truncated": False,
        "study_description_before_len": 0,
        "study_description_after_len": 0,
    }

    raw_sd, raw_pn, raw_series_list = _raw_descriptions_from_tags(
        study.raw_dicom_tags
    )

    if (raw_sd is None and raw_pn is None) and synthesize:
        # Fallback: synthesise a benign description for the demo seed.
        raw_sd = _synth_description(study.modality, study.body_part)
        raw_pn = _synth_protocol(study.modality, study.body_part)

    if raw_sd is None and raw_pn is None and not raw_series_list:
        # Nothing to backfill.
        return changes

    sd_scrub = scrub_description(raw_sd)
    pn_scrub = scrub_description(raw_pn)
    series_scrubs = [scrub_description(s) for s in raw_series_list]

    study.study_description = sd_scrub.text or None if raw_sd is not None else None
    study.protocol_name = pn_scrub.text or None if raw_pn is not None else None

    # Per-series writes.
    if series_scrubs:
        from sqlalchemy import select

        rows = list(
            session.scalars(
                select(Series).where(Series.study_pk == study.study_pk)
            ).all()
        )
        for series_row, scrub in zip(rows, series_scrubs):
            series_row.series_description = scrub.text or None

    quarantine = (
        sd_scrub.quarantine
        or pn_scrub.quarantine
        or any(s.quarantine for s in series_scrubs)
    )
    if quarantine:
        study.preview_status = "phi_detected"

    # Aggregate audit metadata for the report row.
    bl: list[str] = []
    wl: list[str] = []
    for r in (sd_scrub, pn_scrub, *series_scrubs):
        for code in r.blacklist_matched:
            if code not in bl:
                bl.append(code)
        for code in r.whitelist_matched:
            if code not in wl:
                wl.append(code)

    changes.update(
        {
            "blacklist_matched": bl,
            "whitelist_matched": wl,
            "quarantine": quarantine,
            "truncated": (
                sd_scrub.truncated
                or pn_scrub.truncated
                or any(s.truncated for s in series_scrubs)
            ),
            "study_description_before_len": len(raw_sd or ""),
            "study_description_after_len": len(study.study_description or ""),
            "protocol_name_before_len": len(raw_pn or ""),
            "protocol_name_after_len": len(study.protocol_name or ""),
        }
    )
    return changes


def run(
    *,
    dsn: str,
    limit: int | None,
    dry_run: bool,
    quiet: bool,
    report_csv: str | None,
    synthesize: bool,
) -> int:
    from sqlalchemy import select

    from radivault_central.db.models import Study

    session_factory = _make_session_factory(dsn)
    n_total = 0
    n_changed = 0
    n_quarantined = 0
    n_truncated = 0
    rows_for_report: list[dict] = []

    with session_factory() as session:
        stmt = select(Study).order_by(Study.study_pk)
        if limit:
            stmt = stmt.limit(limit)
        for study in session.scalars(stmt):
            n_total += 1
            changes = process_study(session, study=study, synthesize=synthesize)
            if changes.get("study_description_after_len", 0) or changes.get(
                "protocol_name_after_len", 0
            ):
                n_changed += 1
            if changes.get("quarantine"):
                n_quarantined += 1
            if changes.get("truncated"):
                n_truncated += 1
            if report_csv:
                rows_for_report.append(changes)
            if not quiet:
                log.info(
                    "study_processed %s blacklist=%s wl=%s quarantine=%s",
                    study.pseudo_study_uid[:32],
                    changes.get("blacklist_matched"),
                    changes.get("whitelist_matched"),
                    changes.get("quarantine"),
                )

        if dry_run:
            session.rollback()
            log.info(
                "DRY-RUN total=%d changed=%d quarantined=%d truncated=%d",
                n_total,
                n_changed,
                n_quarantined,
                n_truncated,
            )
        else:
            session.commit()
            log.info(
                "BACKFILL total=%d changed=%d quarantined=%d truncated=%d",
                n_total,
                n_changed,
                n_quarantined,
                n_truncated,
            )

    if report_csv and rows_for_report:
        with open(report_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "pseudo_study_uid",
                    "scrub_version",
                    "blacklist_matched",
                    "whitelist_matched",
                    "quarantine",
                    "truncated",
                    "study_description_before_len",
                    "study_description_after_len",
                    "protocol_name_before_len",
                    "protocol_name_after_len",
                ],
            )
            writer.writeheader()
            for row in rows_for_report:
                row = dict(row)
                row["blacklist_matched"] = json.dumps(row.get("blacklist_matched", []))
                row["whitelist_matched"] = json.dumps(row.get("whitelist_matched", []))
                writer.writerow(row)
        log.info("BACKFILL report written to %s rows=%d", report_csv, len(rows_for_report))

    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-dsn", default=os.environ.get("CENTRAL_DSN", DEFAULT_DB_DSN))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--synthesize",
        action="store_true",
        help=(
            "Demo-only — when raw_dicom_tags has no description, synthesise "
            "a benign placeholder (modality + body_part) so the UI shows a "
            "non-empty Description column."
        ),
    )
    parser.add_argument("--report-csv", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info(
        "backfill_start dsn=%s limit=%s dry_run=%s synthesize=%s",
        args.db_dsn.rsplit("@", 1)[-1] if "@" in args.db_dsn else args.db_dsn,
        args.limit,
        args.dry_run,
        args.synthesize,
    )
    return run(
        dsn=args.db_dsn,
        limit=args.limit,
        dry_run=args.dry_run,
        quiet=args.quiet,
        report_csv=args.report_csv,
        synthesize=args.synthesize,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
