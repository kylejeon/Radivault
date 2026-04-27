"""``GET /v1/search/autocomplete`` (text-search-description FR-TS-8).

Buyer-facing trigram-based suggestion endpoint backed by ``pg_trgm``'s
``word_similarity`` operator and the GIN index created by alembic
``0008_text_search_safe_fields``.

Phase 1.0 surface (no description text — Kyle PHI policy):
- ``body_part``    (top suggestion source)
- ``modality``     (short codes — MR, CT, …)
- ``kcd_label_en`` (English diagnostic label)
- ``kcd_label_ko`` (Korean diagnostic label)
- ``manufacturer`` (vendor name)

Each row carries the matching ``field`` so the dropdown can render a small
badge. Hard cap of 12 (design-spec §7.1) — the buyer-supplied ``limit`` is
clamped before reaching the SQL.

Auth + global rate limit reuse the existing middleware stack
(``BuyerAuthMiddleware`` + ``RateLimitMiddleware`` in ``app.py``). No
per-route limiter is needed for Phase 1.0; if abuse is observed Phase 2 will
add a slowapi route-scoped cap.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Iterable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from radivault_central.db.models import Study
from radivault_search.auth.middleware import require_buyer
from radivault_search.query.schema import (
    AutocompleteResponse,
    AutocompleteSuggestion,
)

router = APIRouter()


# Fields scanned for trigram matches. Order is also the badge fallback order.
#
# text-search-description Phase 1.5 (FR-TS15-7) — adds study_description +
# protocol_name. These render with STUDY DESC / PROTOCOL badges in the
# dropdown (design-spec §11.1). description fields are skipped when the
# description-extraction feature flag is OFF (no point fetching empties).
_AUTOCOMPLETE_FIELDS: tuple[str, ...] = (
    "study_description",
    "protocol_name",
    "body_part",
    "modality",
    "kcd_label_en",
    "kcd_label_ko",
    "manufacturer",
)


def _description_extraction_enabled() -> bool:
    raw = os.environ.get("DESCRIPTION_EXTRACTION_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _autocomplete_fields_for_request() -> tuple[str, ...]:
    if _description_extraction_enabled():
        return _AUTOCOMPLETE_FIELDS
    # Drop description fields when the flag is off so the dropdown stays
    # backward-compatible with Phase 1.0 contract.
    return tuple(
        f for f in _AUTOCOMPLETE_FIELDS
        if f not in ("study_description", "protocol_name")
    )

# Trigram word_similarity threshold — recall-first per research §3.2.
_TRGM_THRESHOLD: float = 0.25

# Hard cap regardless of buyer-supplied limit (design-spec §7.1).
_MAX_LIMIT: int = 12


def _text_search_enabled() -> bool:
    raw = os.environ.get("TEXT_SEARCH_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _dedupe_keep_order(items: Iterable[AutocompleteSuggestion]) -> list[AutocompleteSuggestion]:
    seen: set[tuple[str, str]] = set()
    out: list[AutocompleteSuggestion] = []
    for it in items:
        key = (it.text.casefold(), it.field)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


@router.get("/v1/search/autocomplete")
async def search_autocomplete(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=_MAX_LIMIT),
) -> JSONResponse:
    """text-search-description FR-TS-8 — trigram-backed suggestion endpoint."""
    require_buyer(request)  # 401 on missing/bad auth.

    if not _text_search_enabled():
        # FR-TS-14 — rolled-back state. Match the search router's silent-skip
        # ergonomics: return an empty suggestions array (clients render the
        # dropdown as "no suggestions") rather than 503-ing the typing flow.
        return JSONResponse(
            status_code=200,
            content=AutocompleteResponse(
                suggestions=[], computed_at=datetime.now(tz=UTC)
            ).model_dump(mode="json"),
        )

    q_clean = (q or "").strip()
    if not q_clean:
        raise HTTPException(
            status_code=400,
            detail={"error": "ERR_INVALID_QUERY", "detail": "q must not be empty"},
        )

    factory = request.app.state.session_factory
    effective_limit = min(int(limit), _MAX_LIMIT)
    suggestions: list[AutocompleteSuggestion] = []

    with factory() as session:
        dialect_name = session.bind.dialect.name if session.bind is not None else "sqlite"

        if dialect_name == "postgresql":
            # Postgres path — trigram word_similarity with the GIN index.
            # We probe each field with the same threshold and merge results,
            # rather than stitching the columns into a single concatenation,
            # so the ``field`` badge stays accurate.
            for field_name in _autocomplete_fields_for_request():
                sql = text(
                    f"""
                    SELECT DISTINCT
                      {field_name} AS suggestion,
                      word_similarity(:q, {field_name}) AS score
                      FROM study
                     WHERE {field_name} IS NOT NULL
                       AND {field_name} <> ''
                       AND word_similarity(:q, {field_name}) >= :threshold
                     ORDER BY score DESC, suggestion ASC
                     LIMIT :per_field
                    """
                ).bindparams(
                    q=q_clean,
                    threshold=_TRGM_THRESHOLD,
                    per_field=effective_limit,
                )
                try:
                    for row in session.execute(sql).all():
                        if row.suggestion is None:
                            continue
                        suggestions.append(
                            AutocompleteSuggestion(
                                text=str(row.suggestion),
                                field=field_name,
                                score=float(row.score or 0.0),
                            )
                        )
                except Exception:  # pragma: no cover — defensive
                    # pg_trgm extension missing or column absent — fall through
                    # to the next field rather than 500-ing the typing flow.
                    continue
        else:
            # SQLite test fallback — case-insensitive substring match across
            # the same fields, with a stable score so unit tests can assert
            # a deterministic order.
            from sqlalchemy import func, select

            like = f"%{q_clean}%"
            for field_name in _autocomplete_fields_for_request():
                col = getattr(Study, field_name, None)
                if col is None:
                    continue
                stmt = (
                    select(col)
                    .where(col.is_not(None))
                    .where(func.lower(col).like(like.lower()))
                    .distinct()
                    .limit(effective_limit)
                )
                for value in session.scalars(stmt).all():
                    if not value:
                        continue
                    suggestions.append(
                        AutocompleteSuggestion(
                            text=str(value),
                            field=field_name,
                            # Crude length-based score so longer matches win.
                            score=round(len(q_clean) / max(len(value), 1), 4),
                        )
                    )

    suggestions.sort(key=lambda s: s.score, reverse=True)
    deduped = _dedupe_keep_order(suggestions)[:effective_limit]

    resp = AutocompleteResponse(
        suggestions=deduped,
        computed_at=datetime.now(tz=UTC),
    )
    return JSONResponse(status_code=200, content=resp.model_dump(mode="json"))
