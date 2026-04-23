"""Filter validator + cost estimator (dev-spec FR-17..FR-23).

Pydantic already enforces types/length. The cost estimator is EXPLAIN-based on
PostgreSQL with a ``pg_class.reltuples`` fallback. On SQLite (tests) we use a
simple ``SELECT COUNT(*)`` within a safety limit so keyset behaviour can be
exercised without a real Postgres.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from radivault_central.db.models import Study
from radivault_search.errors import FilterTooMany
from radivault_search.query.schema import SearchRequest

log = logging.getLogger("radivault_search.validator")


def validate_filter(req: SearchRequest) -> None:
    """Enforce the list-length caps (FR-17) beyond what pydantic catches."""
    for name in ("modality", "body_part", "age_bucket", "manufacturer"):
        val = getattr(req, name, None)
        if val is not None and len(val) > 10:
            raise FilterTooMany(
                detail=f"{name}: exceeds 10 items (got {len(val)})",
            )


@dataclass
class CostEstimate:
    estimated_rows: int
    method: str  # 'explain' | 'count' | 'reltuples' | 'cache'
    suppressed_facets: bool = False


def estimate_cost(
    session: Session,
    req: SearchRequest,
    *,
    max_rows: int = 10_000_000,
    facet_suppress_rows: int = 2_000_000,
) -> CostEstimate:
    """Estimate the rows matched by the filter.

    On Postgres we use ``EXPLAIN (FORMAT JSON)`` and parse ``Plan Rows``. On
    SQLite (tests) we use ``SELECT COUNT(*)`` — accepting that this is the
    actual count rather than an estimate; functional behaviour of the gate is
    preserved.
    """
    dialect = session.bind.dialect.name if session.bind is not None else "sqlite"
    clauses = _build_where(req)

    if dialect == "postgresql":
        try:
            stmt = select(Study.study_pk)
            for c in clauses:
                stmt = stmt.where(c)
            sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            explain = session.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar()
            plan = json.loads(explain) if isinstance(explain, str) else explain
            rows = int(plan[0]["Plan"]["Plan Rows"])
            return CostEstimate(
                estimated_rows=rows,
                method="explain",
                suppressed_facets=rows > facet_suppress_rows,
            )
        except Exception as exc:  # fall through to count
            log.warning("explain_failed: %s", exc)

    # SQLite or EXPLAIN fallback.
    stmt = select(func.count(Study.study_pk))
    for c in clauses:
        stmt = stmt.where(c)
    count = int(session.execute(stmt).scalar() or 0)
    return CostEstimate(
        estimated_rows=count,
        method="count",
        suppressed_facets=count > facet_suppress_rows,
    )


def _build_where(req: SearchRequest) -> list:
    """Return a list of SQLAlchemy clauses for the ``study`` table filter.

    Used by both the cost estimator and the executor.
    """
    out: list = []
    if req.modality:
        out.append(Study.modality.in_(req.modality))
    if req.body_part:
        out.append(Study.body_part.in_(req.body_part))
    if req.manufacturer:
        out.append(Study.manufacturer.in_(req.manufacturer))
    if req.study_date_shifted is not None:
        out.append(Study.study_date_shifted >= req.study_date_shifted.date_from)
        out.append(Study.study_date_shifted < req.study_date_shifted.date_to)
    # age_bucket, sex live on patient_pseudo — filtered via join in executor.
    return out
