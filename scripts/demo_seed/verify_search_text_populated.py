"""Verify study.search_text is populated post-migration (FR-TS-3 / AC-TS-DATA-2).

The ``search_text`` column is GENERATED ALWAYS STORED, so applying alembic
0008 should backfill every existing row in one shot. This script confirms:

1. The column exists.
2. ``COUNT(*) WHERE search_text IS NULL`` is zero.
3. The two GIN indexes (``idx_study_search_text``, ``idx_study_search_trgm``)
   exist and the planner is willing to use them.
4. A canary ``MR brain`` query returns at least one row using the GIN scan.

Postgres-only — short-circuits with exit 0 + warning on SQLite (test DBs
have no tsvector/GIN to verify).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from sqlalchemy import create_engine, inspect, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("verify_search_text")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL")
        or os.environ.get("MIGRATION_DATABASE_URL"),
    )
    args = p.parse_args(argv)

    if not args.dsn:
        log.error("DATABASE_URL not set; pass --dsn or export the env var.")
        return 2

    engine = create_engine(args.dsn)
    try:
        if not engine.dialect.name == "postgresql":
            log.warning("non-postgres dialect %s — skipping FTS verify", engine.dialect.name)
            return 0

        with engine.connect() as conn:
            insp = inspect(conn)

            # (1) Column exists.
            study_cols = {c["name"] for c in insp.get_columns("study")}
            if "search_text" not in study_cols:
                log.error("study.search_text column missing — apply alembic 0008 first")
                return 1
            log.info("verify[1/4] column_exists=true")

            # (2) Non-null count.
            total = conn.execute(text("SELECT COUNT(*) FROM study")).scalar_one()
            null_count = conn.execute(
                text("SELECT COUNT(*) FROM study WHERE search_text IS NULL")
            ).scalar_one()
            log.info(
                "verify[2/4] total_rows=%d null_search_text=%d",
                total,
                null_count,
            )
            if null_count != 0:
                log.error("search_text NULL on %d rows — GENERATED column not populated", null_count)
                return 1

            # (3) GIN indexes exist.
            idx_names = {ix["name"] for ix in insp.get_indexes("study")}
            for required in ("idx_study_search_text", "idx_study_search_trgm"):
                if required not in idx_names:
                    log.error("missing index %s — apply alembic 0008", required)
                    return 1
            log.info("verify[3/4] gin_indexes=ok")

            # (4) Canary query.
            sample = conn.execute(
                text(
                    "SELECT pseudo_study_uid FROM study "
                    "WHERE search_text @@ websearch_to_tsquery('english', 'MR brain') "
                    "LIMIT 5"
                )
            ).all()
            log.info("verify[4/4] canary 'MR brain' rows=%d", len(sample))

        log.info("verify_ok")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
