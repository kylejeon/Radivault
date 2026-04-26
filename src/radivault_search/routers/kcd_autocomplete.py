"""``GET /v1/search/kcd-autocomplete`` (dev-spec-buyer-search-v3 FR-V3-API-4).

Triple-ontology autocomplete (KCD-8 / SNOMED / RadLex) backed by a static
in-memory dictionary (``radivault_search.query.kcd_dict``). Buyer bearer auth
required (same gate as ``/v1/search/studies``). Rate limit is enforced by
the ``RateLimitMiddleware`` already wired into the app — no per-route logic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from radivault_search.auth.middleware import require_buyer
from radivault_search.query.kcd_dict import search as kcd_search
from radivault_search.query.schema import (
    KCDAutocompleteItem,
    KCDAutocompleteResponse,
)

router = APIRouter()


@router.get("/v1/search/kcd-autocomplete")
async def kcd_autocomplete(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(12, ge=1, le=50),
) -> JSONResponse:
    require_buyer(request)  # 401 on missing/bad auth.
    q_clean = (q or "").strip()
    if not q_clean:
        raise HTTPException(
            status_code=400,
            detail={"error": "ERR_INVALID_QUERY", "detail": "q must not be empty"},
        )
    matches = kcd_search(q_clean, limit=limit)
    items = [
        KCDAutocompleteItem(
            ontology=m.ontology,
            code=m.code,
            label_ko=m.label_ko,
            label_en=m.label_en,
        )
        for m in matches
    ]
    resp = KCDAutocompleteResponse(items=items, computed_at=datetime.now(tz=UTC))
    return JSONResponse(status_code=200, content=resp.model_dump(mode="json"))
