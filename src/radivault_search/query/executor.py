"""Main query execution — keyset pagination + facets + total count.

See dev-spec §4.4 / §4.5 / §4.6. This module intentionally orchestrates all
five concerns (filter/sort/limit/facets/total) in a single class so tests can
exercise the stitching end-to-end without standing up FastAPI.

v3 (dev-spec-buyer-search-v3 FR-V3-API-2/5):
- Joins ``hospital`` so ``region_pseudo`` is selectable + filterable.
- Adds 9 sort columns (hospital, modality, body_part, kcd, age, mfg, model,
  size, date_asc).
- Surfaces v3 fields onto ``StudyItem``.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.orm import Session

from radivault_central.db.models import Hospital, PatientPseudo, Study
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


# v3 — sort key → (column, direction). Direction is `desc` / `asc`.
def _sort_column_and_dir(sort_key: str):
    mapping = {
        "date_desc": (Study.study_date_shifted, desc),
        "date_asc": (Study.study_date_shifted, asc),
        "ingested_desc": (Study.ingested_at, desc),
        "hospital_asc": (Study.hospital_pk, asc),
        "hospital_desc": (Study.hospital_pk, desc),
        "modality_asc": (Study.modality, asc),
        "modality_desc": (Study.modality, desc),
        "body_part_asc": (Study.body_part, asc),
        "body_part_desc": (Study.body_part, desc),
        "kcd_asc": (Study.kcd_code, asc),
        "kcd_desc": (Study.kcd_code, desc),
        "age_asc": (PatientPseudo.age, asc),
        "age_desc": (PatientPseudo.age, desc),
        "manufacturer_asc": (Study.manufacturer, asc),
        "manufacturer_desc": (Study.manufacturer, desc),
        "model_asc": (Study.model_name, asc),
        "model_desc": (Study.model_name, desc),
        "size_asc": (Study.total_bytes, asc),
        "size_desc": (Study.total_bytes, desc),
    }
    return mapping.get(sort_key, (Study.study_date_shifted, desc))


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
    """Apply joins for patient_pseudo (sex/age) + hospital (region_pseudo).

    v3 — hospital is always joined so ``region_pseudo`` is in the SELECT
    projection; patient_pseudo is joined only when sex/age filters apply or
    age sort is requested. Both are LEFT joins to preserve study rows
    missing those linkages.
    """
    sort_uses_age = req.sort in ("age_asc", "age_desc")
    needs_patient = (
        bool(req.sex)
        or bool(req.age_bucket)
        or req.age_min is not None
        or req.age_max is not None
        or sort_uses_age
    )
    if needs_patient:
        stmt = stmt.join(
            PatientPseudo,
            PatientPseudo.patient_pseudo_pk == Study.patient_pseudo_pk,
            isouter=True,
        )
        if req.sex:
            stmt = stmt.where(PatientPseudo.sex.in_(req.sex))
        if req.age_bucket and req.age_min is None and req.age_max is None:
            # Legacy bucket filter (deprecated, only honoured when no exact range).
            numeric = []
            for v in req.age_bucket:
                try:
                    numeric.append(int(str(v).split("-")[0]))
                except ValueError:
                    continue
            if numeric:
                stmt = stmt.where(PatientPseudo.age_bucket.in_(numeric))
        if req.age_min is not None:
            stmt = stmt.where(PatientPseudo.age >= req.age_min)
        if req.age_max is not None:
            stmt = stmt.where(PatientPseudo.age <= req.age_max)

    # v3 — always LEFT JOIN hospital so region_pseudo + region filter are
    # available. Hospital filter applied here.
    stmt = stmt.join(
        Hospital, Hospital.hospital_pk == Study.hospital_pk, isouter=True
    )
    if req.hospital_region:
        stmt = stmt.where(Hospital.region_pseudo.in_(req.hospital_region))
    return stmt


def run_search(
    session: Session,
    req: SearchRequest,
    *,
    buyer_pk: int,
    global_salt: str,
    include_facets_override: bool | None = None,
    facets_suppressed: bool = False,
    scope_json: dict | None = None,
    buyer_tier: str | None = None,
    buyer_quota_remaining: int | None = None,
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

    where_clauses = _build_where(req, scope_json=scope_json)

    # Main page query.
    stmt = select(Study).where(*where_clauses)
    stmt = _apply_patient_joins(stmt, req)

    sort_col, sort_dir = _sort_column_and_dir(req.sort)

    # Keyset WHERE clause (only for date_desc/ingested_desc legacy sorts —
    # cursor pagination on the new sort enums is left for v0.1.5 + only
    # validated against demo workloads of 250 rows).
    if cursor_d is not None and cursor_p is not None and req.sort in (
        "date_desc",
        "ingested_desc",
    ):
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

    # Stable secondary sort on study_pk so ties are deterministic.
    secondary = desc(Study.study_pk) if sort_dir is desc else asc(Study.study_pk)
    stmt = stmt.order_by(sort_dir(sort_col), secondary).limit(req.limit + 1)

    rows = list(session.scalars(stmt).all())
    has_more = len(rows) > req.limit
    page_rows = rows[: req.limit]

    items = []
    for r in page_rows:
        pp = (
            session.get(PatientPseudo, r.patient_pseudo_pk)
            if r.patient_pseudo_pk is not None
            else None
        )
        hosp = session.get(Hospital, r.hospital_pk)
        items.append(
            StudyItem(
                pseudo_study_uid=r.pseudo_study_uid,
                modality=r.modality,
                body_part=r.body_part,
                age_bucket=_age_bucket_label_from(pp),
                sex=pp.sex if pp is not None else None,
                study_date_shifted=r.study_date_shifted.date()
                if hasattr(r.study_date_shifted, "date")
                else r.study_date_shifted,
                manufacturer=r.manufacturer,
                model_name=r.model_name,
                n_instances=r.n_instances,
                n_series=r.n_series,
                total_bytes=r.total_bytes,
                hospital_opaque_id=compute_hospital_opaque_id(
                    hospital_pk=r.hospital_pk,
                    global_salt=global_salt,
                    buyer_pk=buyer_pk,
                ),
                ingested_at=r.ingested_at,
                preview_status=getattr(r, "preview_status", None),
                preview_slice_count=getattr(r, "preview_slice_count", None),
                # v3 fields.
                patient_age=pp.age if pp is not None else None,
                hospital_region_pseudo=hosp.region_pseudo if hosp is not None else None,
                kcd_code=getattr(r, "kcd_code", None),
                kcd_label_ko=getattr(r, "kcd_label_ko", None),
                kcd_label_en=getattr(r, "kcd_label_en", None),
            )
        )

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

    # Build next_cursor if more pages exist (legacy sort modes only).
    next_cursor: str | None = None
    if (
        has_more
        and page_rows
        and req.sort in ("date_desc", "ingested_desc")
    ):
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
        buyer_quota_remaining=buyer_quota_remaining,
        buyer_tier=buyer_tier,
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
        hint=hint_str,
    )
    # attach cursor_presence for audit
    response.__dict__["_cursor_presence"] = cursor_presence

    return ExecutorResult(
        response=response,
        total_count=total_count,
        facets_suppressed=facets_suppressed,
    )


# ---------------------------------------------------------------------------


def _age_bucket_label_from(pp: PatientPseudo | None) -> str | None:
    if pp is None or pp.age_bucket is None:
        return None
    lo = int(pp.age_bucket)
    return f"{lo}-{lo + 10}"


def _age_bucket_label(session: Session, patient_pk: int | None) -> str | None:
    """Legacy single-row helper — retained for ``load_study_detail``."""
    if patient_pk is None:
        return None
    pp = session.get(PatientPseudo, patient_pk)
    return _age_bucket_label_from(pp)


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
    pp = (
        session.get(PatientPseudo, study.patient_pseudo_pk)
        if study.patient_pseudo_pk is not None
        else None
    )
    hosp = session.get(Hospital, study.hospital_pk)
    return SearchStudyDetail(
        pseudo_study_uid=study.pseudo_study_uid,
        modality=study.modality,
        body_part=study.body_part,
        age_bucket=_age_bucket_label_from(pp),
        sex=pp.sex if pp is not None else None,
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
        preview_status=getattr(study, "preview_status", None),
        preview_slice_count=getattr(study, "preview_slice_count", None),
        patient_age=pp.age if pp is not None else None,
        hospital_region_pseudo=hosp.region_pseudo if hosp is not None else None,
        kcd_code=getattr(study, "kcd_code", None),
        kcd_label_ko=getattr(study, "kcd_label_ko", None),
        kcd_label_en=getattr(study, "kcd_label_en", None),
    )
