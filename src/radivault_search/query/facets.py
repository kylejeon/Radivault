"""Whitelisted facet aggregation (dev-spec §4.5, FR-31..FR-34).

Six fields only: modality, body_part, sex, age_bucket, manufacturer, year.

``age_bucket`` / ``sex`` live on ``patient_pseudo``; the queries below join
that table. ``year`` is derived from ``study_date_shifted``.
"""

from __future__ import annotations

from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from radivault_central.db.models import PatientPseudo, Study
from radivault_search.query.schema import FacetValue

FACET_FIELDS = (
    "modality",
    "body_part",
    "sex",
    "age_bucket",
    "manufacturer",
    "year",
)

MAX_BUCKETS = 50


def compute_facets(
    session: Session,
    *,
    where_clauses: list,
    dialect: str,
) -> dict[str, list[FacetValue]]:
    """Run the 6 GROUP BY queries and shape the output.

    Each field executes a single grouped SELECT and truncates at 50 buckets.
    The remainder (if any) rolls up into a ``__other__`` row.
    """
    result: dict[str, list[FacetValue]] = {}

    base_filters = list(where_clauses)

    # Simple string-valued facets.
    for field in ("modality", "body_part", "manufacturer"):
        col = getattr(Study, field)
        stmt = (
            select(col, func.count(Study.study_pk))
            .where(*base_filters)
            .group_by(col)
            .order_by(desc(func.count(Study.study_pk)))
        )
        rows = session.execute(stmt).all()
        result[field] = _shape_rows(rows)

    # sex / age_bucket come from patient_pseudo.
    sex_stmt = (
        select(PatientPseudo.sex, func.count(Study.study_pk))
        .select_from(Study)
        .join(
            PatientPseudo,
            PatientPseudo.patient_pseudo_pk == Study.patient_pseudo_pk,
            isouter=True,
        )
        .where(*base_filters)
        .group_by(PatientPseudo.sex)
        .order_by(desc(func.count(Study.study_pk)))
    )
    result["sex"] = _shape_rows(session.execute(sex_stmt).all())

    age_stmt = (
        select(PatientPseudo.age_bucket, func.count(Study.study_pk))
        .select_from(Study)
        .join(
            PatientPseudo,
            PatientPseudo.patient_pseudo_pk == Study.patient_pseudo_pk,
            isouter=True,
        )
        .where(*base_filters)
        .group_by(PatientPseudo.age_bucket)
        .order_by(desc(func.count(Study.study_pk)))
    )
    # age_bucket is SmallInteger on the central ORM — stringify for response.
    rows = [(str(v) if v is not None else None, c) for v, c in session.execute(age_stmt).all()]
    result["age_bucket"] = _shape_rows(rows)

    # year — derive from study_date_shifted (ISO year).
    if dialect == "sqlite":
        year_expr = func.strftime("%Y", Study.study_date_shifted)
    else:
        year_expr = func.extract("year", Study.study_date_shifted)
    # Cast to text for deterministic output.
    year_stmt = (
        select(year_expr, func.count(Study.study_pk))
        .where(*base_filters)
        .group_by(year_expr)
        .order_by(desc(func.count(Study.study_pk)))
    )
    raw = session.execute(year_stmt).all()
    normalized = []
    for v, c in raw:
        if v is None:
            normalized.append((None, c))
        else:
            # strftime gives str '2026'; extract gives float 2026.0
            s = str(int(float(v))) if isinstance(v, (int, float)) else str(v)
            normalized.append((s, c))
    result["year"] = _shape_rows(normalized)

    # Silence "case" import warning on ruff.
    _ = case

    return result


def _shape_rows(rows) -> list[FacetValue]:
    """Clamp to MAX_BUCKETS and append ``__other__`` summary if needed."""
    items = [(val, int(count or 0)) for val, count in rows]
    items.sort(key=lambda it: it[1], reverse=True)
    top = items[:MAX_BUCKETS]
    rest = items[MAX_BUCKETS:]
    out = [FacetValue(value=v, count=c, is_truncated=False) for v, c in top]
    if rest:
        out.append(FacetValue(value="__other__", count=sum(c for _, c in rest), is_truncated=True))
    return out
