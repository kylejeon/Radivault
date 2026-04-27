"""Daily cleanup of search_audit.raw_query > 30 days old (FR-TS-10).

Buyer-typed search queries can contain PHI even after the on-write scrub
flagged the obvious patterns. PIPA §28-8 caps the retention budget for
free-text PHI evidence — we honour that with a 30-day TTL on the
``raw_query`` column, while keeping the masked copy + pattern flags
forever for security audit.

Usage::

    # Dry run — print the row count that *would* be cleared.
    python scripts/ops/cleanup_search_audit_raw.py --dry-run

    # Apply — UPDATE search_audit SET raw_query=NULL WHERE created_at < ...
    python scripts/ops/cleanup_search_audit_raw.py

    # Override the TTL window (default 30 days).
    python scripts/ops/cleanup_search_audit_raw.py --days 14

Cron registration outline (systemd timer or k8s CronJob — both supported,
operator chooses one based on deployment topology). Example k8s manifest::

    apiVersion: batch/v1
    kind: CronJob
    metadata:
      name: search-audit-raw-cleanup
    spec:
      schedule: "17 3 * * *"  # 03:17 KST daily
      jobTemplate:
        spec:
          template:
            spec:
              containers:
                - name: cleanup
                  image: radivault/search:latest
                  command:
                    - python
                    - /app/scripts/ops/cleanup_search_audit_raw.py
                  env:
                    - name: DATABASE_URL
                      valueFrom: { secretKeyRef: { name: rv-db, key: dsn } }
              restartPolicy: OnFailure
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cleanup_search_audit_raw")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--days",
        type=int,
        default=30,
        help="Retention window in days (default 30 — PIPA §28-8 alignment).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the SELECT COUNT(*) of rows that would be cleared, then exit.",
    )
    p.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL")
        or os.environ.get("MIGRATION_DATABASE_URL"),
        help="SQLAlchemy DSN — defaults to $DATABASE_URL or $MIGRATION_DATABASE_URL.",
    )
    args = p.parse_args(argv)

    if not args.dsn:
        log.error("DATABASE_URL not set; pass --dsn or export the env var.")
        return 2

    cutoff = datetime.now(tz=UTC) - timedelta(days=args.days)
    log.info("ttl_cutoff_utc=%s days=%d dry_run=%s", cutoff.isoformat(), args.days, args.dry_run)

    engine = create_engine(args.dsn)
    try:
        with engine.begin() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM search_audit "
                    "WHERE created_at < :cutoff AND raw_query IS NOT NULL"
                ),
                {"cutoff": cutoff},
            ).scalar_one()
            log.info("candidate_rows=%d", count)
            if args.dry_run:
                log.info("dry_run — no UPDATE issued")
                return 0
            if count == 0:
                log.info("nothing_to_clear")
                return 0
            result = conn.execute(
                text(
                    "UPDATE search_audit SET raw_query = NULL "
                    "WHERE created_at < :cutoff AND raw_query IS NOT NULL"
                ),
                {"cutoff": cutoff},
            )
            log.info("rows_cleared=%d", result.rowcount or 0)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
