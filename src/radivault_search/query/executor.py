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
import os
import time
from dataclasses import dataclass

from sqlalchemy import and_, asc, desc, func, literal_column, or_, select, text
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


def text_search_enabled() -> bool:
    """text-search-description FR-TS-14 — env-driven kill switch.

    ``TEXT_SEARCH_ENABLED=false`` (case-insensitive) makes the executor
    silently ignore ``req.q`` so a runtime issue can be rolled back in
    < 30 s without redeploying. Default is ``true``.
    """
    raw = os.environ.get("TEXT_SEARCH_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


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

    # text-search-description FR-TS-2 / FR-TS-14 — resolve effective q.
    # Empty / blank q is coerced to None by the schema validator.
    flag_on = text_search_enabled()
    effective_q: str | None = req.q if (req.q and flag_on) else None
    dialect_name = session.bind.dialect.name if session.bind is not None else "sqlite"

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

    # FR-TS-3 / FR-TS-13 — append the FTS predicate to the WHERE list so the
    # cost estimator (which calls ``_build_where`` directly) is unaware of
    # text search, while the executor + count both honour the same predicate.
    if effective_q is not None:
        if dialect_name == "postgresql":
            where_clauses = list(where_clauses) + [
                text(
                    "study.search_text @@ websearch_to_tsquery('english', :q_text)"
                ).bindparams(q_text=effective_q)
            ]
        else:
            # SQLite test fallback — ILIKE across the same fields the tsvector
            # weights (body_part / kcd_label_*) so unit tests can still exercise
            # the q wiring end-to-end. Each whitespace-split token must match
            # to mimic websearch_to_tsquery's AND semantics.
            from sqlalchemy import or_ as _or

            tokens = [t for t in effective_q.split() if t]
            for tok in tokens:
                like = f"%{tok}%"
                where_clauses = list(where_clauses) + [
                    _or(
                        Study.body_part.ilike(like),
                        Study.kcd_label_en.ilike(like),
                        Study.kcd_label_ko.ilike(like),
                        Study.modality.ilike(like),
                        Study.manufacturer.ilike(like),
                        Study.model_name.ilike(like),
                    )
                ]

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

    # FR-TS-7 — when q is active, ts_rank_cd dominates. The user's existing
    # sort key drops to secondary so ties at equal rank stay deterministic.
    if effective_q is not None and dialect_name == "postgresql":
        rank_expr = text(
            "ts_rank_cd(study.search_text, websearch_to_tsquery('english', :q_rank)) DESC"
        ).bindparams(q_rank=effective_q)
        stmt = stmt.order_by(rank_expr, sort_dir(sort_col), secondary).limit(req.limit + 1)
    else:
        stmt = stmt.order_by(sort_dir(sort_col), secondary).limit(req.limit + 1)

    rows = list(session.scalars(stmt).all())
    has_more = len(rows) > req.limit
    page_rows = rows[: req.limit]

    # FR-TS-9 — server-rendered ts_headline snippet, only on Postgres + q.
    # We compute snippets in a separate trivial query keyed by study_pk so
    # the main keyset stays type-safe (SQLAlchemy ORM scalar load).
    snippet_by_pk: dict[int, str] = {}
    if effective_q is not None and dialect_name == "postgresql" and page_rows:
        pk_list = [r.study_pk for r in page_rows]
        # ``ts_headline`` operates on plain text; we feed it the same
        # concatenation the trigram index covers so the highlight surfaces
        # match what the ranking saw. ``StartSel``/``StopSel`` constrain the
        # injected HTML to a single tag pair (XSS guarded by
        # PostgreSQL-native escape of any other markup; portal also passes
        # the result through DOMPurify before render — FR-TS-9).
        snippet_sql = text(
            """
            SELECT study_pk,
                   ts_headline(
                     'english',
                     coalesce(body_part,'') || ' ' ||
                       coalesce(kcd_label_en,'') || ' ' ||
                       coalesce(kcd_label_ko,'') || ' ' ||
                       coalesce(modality,''),
                     websearch_to_tsquery('english', :q_hl),
                     'MaxFragments=1, MaxWords=12, MinWords=3, '
                     'StartSel=<mark>, StopSel=</mark>'
                   ) AS snippet
              FROM study
             WHERE study_pk = ANY(:pk_list)
            """
        ).bindparams(q_hl=effective_q, pk_list=pk_list)
        try:
            for row in session.execute(snippet_sql).all():
                snippet_by_pk[int(row.study_pk)] = row.snippet
        except Exception:  # pragma: no cover — defensive: never fail the page.
            snippet_by_pk = {}

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
                # FR-TS-9 — populated only on Postgres when q is active.
                highlight_snippet=snippet_by_pk.get(r.study_pk),
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
    # FR-TS-10 — scrub q for the audit copy. The router will pick the patterns
    # off the response (via ``response.__dict__["_text_search_audit"]``) and
    # forward them into the background ``write_audit`` task. This keeps the
    # router shielded from importing ``phi_scrub`` directly.
    phi_patterns: list[str] = []
    masked_q: str | None = None
    if effective_q is not None:
        from radivault_search.audit.phi_scrub import scrub_query as _scrub

        scrub_res = _scrub(effective_q)
        masked_q = scrub_res.masked
        phi_patterns = list(scrub_res.patterns)

    meta = Meta(
        total_hint=total_count,
        total_count_exact=True,
        result_is_approximate=False,
        query_duration_ms=duration_ms,
        buyer_quota_remaining=buyer_quota_remaining,
        buyer_tier=buyer_tier,
        facets_suppressed=facets_suppressed,
        response_truncated=False,
        text_search_applied=effective_q is not None,
        phi_flagged_patterns=phi_patterns,
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
    # FR-TS-10 — attach scrub artefacts for the router's background audit task.
    response.__dict__["_text_search_audit"] = {
        "raw_query": effective_q,
        "masked_query": masked_q,
        "phi_flagged_patterns": phi_patterns,
    }

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
