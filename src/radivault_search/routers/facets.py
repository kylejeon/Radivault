"""``GET /v1/search/facets`` — filter autocompletion (dev-spec §7.3)."""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from radivault_search.auth.middleware import require_buyer
from radivault_search.query.facets import compute_facets
from radivault_search.query.schema import FacetsResponse
from radivault_search.telemetry import CACHE_HIT_TOTAL

log = logging.getLogger("radivault_search.facets")

router = APIRouter()


@router.get("/v1/search/facets")
async def get_facets(request: Request) -> JSONResponse:
    require_buyer(request)  # 401 on missing/bad auth.
    settings = request.app.state.settings
    factory = request.app.state.session_factory
    redis_client = request.app.state.redis

    cache_key = "search:facets:global"
    cached = _get_cache(redis_client, cache_key)
    if cached is not None:
        CACHE_HIT_TOTAL.labels(cache_layer="facets").inc()
        return JSONResponse(status_code=200, content=cached)

    with factory() as session:
        dialect = session.bind.dialect.name if session.bind is not None else "sqlite"
        facets = compute_facets(session, where_clauses=[], dialect=dialect)
    resp = FacetsResponse(
        modality=facets.get("modality", []),
        body_part=facets.get("body_part", []),
        sex=facets.get("sex", []),
        age_bucket=facets.get("age_bucket", []),
        manufacturer=facets.get("manufacturer", []),
        year=facets.get("year", []),
        computed_at=datetime.now(tz=UTC),
    )
    payload = resp.model_dump(mode="json")
    _set_cache(redis_client, cache_key, payload, ttl=settings.redis.facets_cache_ttl_seconds)
    return JSONResponse(status_code=200, content=payload)


def _get_cache(redis_client, key: str):
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(key)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _set_cache(redis_client, key: str, payload, ttl: int) -> None:
    if redis_client is None:
        return
    with contextlib.suppress(Exception):
        redis_client.setex(key, ttl, json.dumps(payload, default=str))
