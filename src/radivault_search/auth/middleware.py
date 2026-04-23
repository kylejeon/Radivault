"""Bearer-auth middleware — attaches ``(buyer_pk, tier, kid)`` to request state.

On authentication failure we raise a :class:`SearchError` and let the central
handler emit the envelope. Successful verification caches the tuple in Redis
for ``auth_cache_ttl_seconds`` (FR-5).
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from radivault_central.errors import CentralError
from radivault_search.auth.buyer_tokens import (
    constant_time_miss,
    parse_bearer,
    verify_buyer_key,
)
from radivault_search.db.repository import get_key_by_kid
from radivault_search.errors import (
    AuthExpired,
    AuthFormat,
    AuthMissing,
    SearchError,
)
from radivault_search.telemetry import AUTH_FAILURES_TOTAL, CACHE_HIT_TOTAL

log = logging.getLogger("radivault_search.auth")


PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/healthz",
        "/readyz",
        "/v1/version",
        "/metrics",
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


class BuyerAuthMiddleware(BaseHTTPMiddleware):
    """Resolve ``Authorization: Bearer <api_key>`` into a buyer context."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        session_factory: Callable,
        redis_client,
        auth_cache_ttl_seconds: int = 60,
        allow_test_prefix: bool = False,
    ) -> None:
        super().__init__(app)
        self._session_factory = session_factory
        self._redis = redis_client
        self._ttl = auth_cache_ttl_seconds
        self._allow_test = allow_test_prefix

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/static/"):
            return await call_next(request)

        try:
            self._authenticate(request)
        except CentralError as exc:
            return _envelope_response(exc, request)
        return await call_next(request)

    # ------------------------------------------------------------------
    def _authenticate(self, request: Request) -> None:
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            AUTH_FAILURES_TOTAL.labels(reason="missing").inc()
            raise AuthMissing()
        bearer = auth.removeprefix("Bearer ").strip()
        parsed = parse_bearer(bearer, allow_test_prefix=self._allow_test)
        if parsed is None:
            AUTH_FAILURES_TOTAL.labels(reason="format").inc()
            raise AuthFormat(detail="API key format invalid")
        kid, prefix = parsed

        # Positive-result cache.
        cached = self._cache_get(kid)
        if cached is not None:
            CACHE_HIT_TOTAL.labels(cache_layer="auth").inc()
            request.state.buyer_pk = cached["buyer_pk"]
            request.state.buyer_id = cached["buyer_id"]
            request.state.tier = cached["tier"]
            request.state.kid = kid
            request.state.scope_json = cached.get("scope_json") or {}
            return

        with self._session_factory() as session:
            row = get_key_by_kid(session, kid)
            if row is None:
                AUTH_FAILURES_TOTAL.labels(reason="kid_not_found").inc()
                constant_time_miss(bearer)
                raise AuthExpired(detail="key not found")
            if row.revoked_at is not None:
                AUTH_FAILURES_TOTAL.labels(reason="revoked").inc()
                raise AuthExpired(detail="key revoked")
            if row.expires_at is not None and row.expires_at < datetime.now(tz=UTC):
                AUTH_FAILURES_TOTAL.labels(reason="expired").inc()
                raise AuthExpired(detail="key expired")
            if not verify_buyer_key(bearer, row.token_hash):
                AUTH_FAILURES_TOTAL.labels(reason="hash_mismatch").inc()
                raise AuthExpired(detail="key hash mismatch")
            buyer = row.buyer
            if buyer is None or not buyer.active:
                AUTH_FAILURES_TOTAL.labels(reason="buyer_inactive").inc()
                raise AuthExpired(detail="buyer inactive")

            ctx = {
                "buyer_pk": buyer.buyer_pk,
                "buyer_id": buyer.buyer_id,
                "tier": row.tier or buyer.tier,
                "scope_json": _merge_scope(buyer.scope_json, row.scope_json),
                "prefix": prefix,
            }
            request.state.buyer_pk = ctx["buyer_pk"]
            request.state.buyer_id = ctx["buyer_id"]
            request.state.tier = ctx["tier"]
            request.state.kid = kid
            request.state.scope_json = ctx["scope_json"]

            row.last_used_at = datetime.now(tz=UTC)
            session.commit()

            self._cache_set(kid, ctx)

    # ------------------------------------------------------------------
    def _cache_get(self, kid: str) -> dict | None:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(f"buyer_auth:{kid}")
        except Exception:
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _cache_set(self, kid: str, ctx: dict) -> None:
        if self._redis is None:
            return
        with contextlib.suppress(Exception):
            self._redis.setex(
                f"buyer_auth:{kid}",
                self._ttl,
                json.dumps(ctx, default=str),
            )


def _merge_scope(buyer_scope: dict | None, key_scope: dict | None) -> dict:
    out: dict = {}
    for src in (buyer_scope or {}, key_scope or {}):
        out.update(src)
    return out


def _envelope_response(exc: CentralError, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    envelope = exc.to_envelope(rid)
    # Rewrite inherited central-ingest doc_url to the search namespace.
    if not isinstance(exc, SearchError):
        envelope["doc_url"] = f"https://docs.radivault.io/search/errors/{exc.code}"
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    if exc.code == "ERR_AUTH_MISSING":
        headers["WWW-Authenticate"] = 'Bearer realm="radivault-search"'
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)


def require_buyer(request: Request) -> tuple[int, str, str, str]:
    """Return ``(buyer_pk, buyer_id, tier, kid)`` from an authed request."""
    buyer_pk = getattr(request.state, "buyer_pk", None)
    buyer_id = getattr(request.state, "buyer_id", None)
    tier = getattr(request.state, "tier", None)
    kid = getattr(request.state, "kid", None)
    if buyer_pk is None or buyer_id is None or tier is None or kid is None:
        raise AuthMissing()
    return buyer_pk, buyer_id, tier, kid
