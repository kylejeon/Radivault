"""Main query execution — keyset pagination + facets + total count.

See dev-spec §4.4 / §4.5 / §4.6. This module intentionally orchestrates all
five concerns (filter/sort/limit/facets/total) in a single class so tests can
exercise the stitching end-to-end without standing up FastAPI.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from radivault_central.db.models import PatientPseudo, Study
from radivault_search.errors import CursorFilterChanged, CursorVersion, StudyNotFound
from radivault_search.query.cursor import (
    CURSOR_VERSION,
    compute_filter_sig,
    decode_cursor,
    encode_cursor,
)
from radivault_search.query.facets import compute_facets
from radivault_search.query.schema import (
    FacetValue,
    Meta,
    Pagination,
    SearchRequest,
    SearchResponse,
    SearchStudyDetail,
    SeriesSummary,
    StudyItem,
    canonical_filter_dict,
)
from radivault_search.query.validator import _build_where


@dataclass
class ExecutorResult:
    response: SearchResponse
    total_count: int
    facets_suppressed: bool


def compute_hospital_opaque_id(
    *,
    hospital_pk: int,
    global_salt: str,
    buyer_pk: int,
) -> str:
    """Per-buyer salted sha256(hospital_pk) → 16 char hex (FR-38)."""
    raw = f"{hospital_pk}|{global_salt}|{buyer_pk}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _apply_patient_joins(stmt, req: SearchRequest):
    needs_patient = bool(req.sex) or bool(req.age_bucket)
    if needs_patient:
        stmt = stmt.join(
            PatientPseudo,
            PatientPseudo.patient_pseudo_pk == Study.patient_pseudo_pk,
            isouter=True,
        )
        if req.sex:
            stmt = stmt.where(PatientPseudo.sex.in_(req.sex))
        if req.age_bucket:
            # age_bucket is stored as SmallInteger on patient_pseudo; accept
            # str or int forms from the buyer.
            numeric = []
            for v in req.age_bucket:
                try:
                    numeric.append(int(str(v).split("-")[0]))
                except ValueError:
                    continue
            if numeric:
                stmt = stmt.where(PatientPseudo.age_bucket.in_(numeric))
    return stmt


def run_search(
    session: Session,
    req: SearchRequest,
    *,
    buyer_pk: int,
    global_salt: str,
    include_facets_override: bool | None = None,
    facets_suppressed: bool = False,
) -> ExecutorResult:
    """Execute the main search — keyset page + facets + total."""
    start = time.perf_counter()

    filter_dict = canonical_filter_dict(req)
    expected_sig = compute_filter_sig(filter_dict, req.sort)

    # Cursor decode + sha check (FR-26/27).
    cursor_d: str | None = None
    cursor_p: int | None = None
    cursor_presence = False
    if req.cursor:
        cursor_presence = True
        try:
            cur = decode_cursor(req.cursor)
        except ValueError as exc:
            raise CursorFilterChanged(detail=f"cursor decode failed: {exc}") from exc
        if cur.v != CURSOR_VERSION:
            raise CursorVersion(detail=f"cursor version={cur.v} not supported")
        if cur.s != expected_sig:
            raise CursorFilterChanged(
                detail="cursor filter_sha256 mismatch; filter changed since cursor issued"
            )
        cursor_d = cur.d
        cursor_p = cur.p

    where_clauses = _build_where(req)

    # Main page query.
    stmt = select(Study).where(*where_clauses)
    stmt = _apply_patient_joins(stmt, req)

    sort_col = Study.ingested_at if req.sort == "ingested_desc" else Study.study_date_shifted

    # Keyset WHERE clause: (sort_col, study_pk) < (cursor_d, cursor_p).
    if cursor_d is not None and cursor_p is not None:
        from datetime import date as _date
        from datetime import datetime as _dt

        if req.sort == "ingested_desc":
            cursor_value = _dt.fromisoformat(cursor_d.replace("Z", "+00:00"))
        else:
            cursor_value = _date.fromisoformat(cursor_d)
        stmt = stmt.where(
            or_(
                sort_col < cursor_value,
                and_(sort_col == cursor_value, Study.study_pk < cursor_p),
            )
        )

    stmt = stmt.order_by(desc(sort_col), desc(Study.study_pk)).limit(req.limit + 1)

    rows = list(session.scalars(stmt).all())
    has_more = len(rows) > req.limit
    page_rows = rows[: req.limit]

    items = [
        StudyItem(
            pseudo_study_uid=r.pseudo_study_uid,
            modality=r.modality,
            body_part=r.body_part,
            age_bucket=_age_bucket_label(session, r.patient_pseudo_pk),
            sex=_sex_for(session, r.patient_pseudo_pk),
            study_date_shifted=r.study_date_shifted.date()
            if hasattr(r.study_date_shifted, "date")
            else r.study_date_shifted,
            manufacturer=r.manufacturer,
            model_name=r.model_name,
            n_instances=r.n_instances,
            n_series=r.n_series,
            total_bytes=r.total_bytes,
            hospital_opaque_id=compute_hospital_opaque_id(
                hospital_pk=r.hospital_pk, global_salt=global_salt, buyer_pk=buyer_pk
            ),
            ingested_at=r.ingested_at,
        )
        for r in page_rows
    ]

    # Exact total count — bounded by cost estimator already (FR-35).
    count_stmt = select(func.count(Study.study_pk)).where(*where_clauses)
    count_stmt = _apply_patient_joins(count_stmt, req)
    total_count = int(session.execute(count_stmt).scalar() or 0)

    # Facets — only if requested + not suppressed.
    want_facets = req.include_facets if include_facets_override is None else include_facets_override
    dialect = session.bind.dialect.name if session.bind is not None else "sqlite"
    facets: dict[str, list[FacetValue]] | None = None
    if want_facets and not facets_suppressed:
        facets = compute_facets(
            session,
            where_clauses=where_clauses,
            dialect=dialect,
        )

    # Build next_cursor if more pages exist.
    next_cursor: str | None = None
    if has_more and page_rows:
        last = page_rows[-1]
        if req.sort == "ingested_desc":
            d_str = last.ingested_at.isoformat() if last.ingested_at is not None else ""
        else:
            d_str = (
                last.study_date_shifted.date().isoformat()
                if hasattr(last.study_date_shifted, "date")
                else str(last.study_date_shifted)
            )
        next_cursor = encode_cursor(
            d=d_str,
            p=last.study_pk,
            filter_sig=expected_sig,
            sort_key=req.sort,
        )

    duration_ms = int((time.perf_counter() - start) * 1000)
    pagination = Pagination(next_cursor=next_cursor, has_more=has_more, page_size=len(items))
    hint_str: str | None = None
    if facets_suppressed and want_facets:
        hint_str = "facets suppressed: cohort too large"
    meta = Meta(
        total_hint=total_count,
        total_count_exact=True,
        result_is_approximate=False,
        query_duration_ms=duration_ms,
        facets_suppressed=facets_suppressed,
        response_truncated=False,
    )
    response = SearchResponse(
        items=items,
        facets=facets,
        pagination=pagination,
        meta=meta,
        total_count=total_count,
        total_count_exact=True,
        next_cursor=next_cursor,
        has_next=has_more,
        page_size=len(items),
        response_truncated=False,
    )
    # Keep hint available via meta / a separate field — inject as attribute.
    response.__pydantic_extra__ = {"hint": hint_str} if hint_str else None
    # attach cursor_presence for audit
    response.__dict__["_cursor_presence"] = cursor_presence

    return ExecutorResult(
        response=response,
        total_count=total_count,
        facets_suppressed=facets_suppressed,
    )


# ---------------------------------------------------------------------------


def _age_bucket_label(session: Session, patient_pk: int | None) -> str | None:
    if patient_pk is None:
        return None
    pp = session.get(PatientPseudo, patient_pk)
    if pp is None or pp.age_bucket is None:
        return None
    lo = int(pp.age_bucket)
    return f"{lo}-{lo + 10}"


def _sex_for(session: Session, patient_pk: int | None) -> str | None:
    if patient_pk is None:
        return None
    pp = session.get(PatientPseudo, patient_pk)
    return pp.sex if pp is not None else None


def load_study_detail(
    session: Session,
    pseudo_study_uid: str,
    *,
    buyer_pk: int,
    global_salt: str,
) -> SearchStudyDetail:
    """Fetch a single study detail by its pseudo UID (§7.2)."""
    study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo_study_uid))
    if study is None:
        raise StudyNotFound(detail=f"pseudo_study_uid={pseudo_study_uid!r} not found")

    from radivault_central.db.models import Series

    series_rows = list(
        session.scalars(select(Series).where(Series.study_pk == study.study_pk)).all()
    )
    series_out = [
        SeriesSummary(
            pseudo_series_uid=s.pseudo_series_uid,
            modality=s.modality,
            n_instances=s.n_instances,
        )
        for s in series_rows
    ]
    return SearchStudyDetail(
        pseudo_study_uid=study.pseudo_study_uid,
        modality=study.modality,
        body_part=study.body_part,
        age_bucket=_age_bucket_label(session, study.patient_pseudo_pk),
        sex=_sex_for(session, study.patient_pseudo_pk),
        study_date_shifted=study.study_date_shifted.date()
        if hasattr(study.study_date_shifted, "date")
        else study.study_date_shifted,
        manufacturer=study.manufacturer,
        model_name=study.model_name,
        n_instances=study.n_instances,
        n_series=study.n_series,
        total_bytes=study.total_bytes,
        hospital_opaque_id=compute_hospital_opaque_id(
            hospital_pk=study.hospital_pk, global_salt=global_salt, buyer_pk=buyer_pk
        ),
        ingested_at=study.ingested_at,
        series=series_out,
    )
