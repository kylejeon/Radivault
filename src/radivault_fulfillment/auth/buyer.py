"""Buyer-plane auth middleware — reuses metadata-index buyer_api_key.

FR-1/2/3/6/7: validates ``Authorization: Bearer rv_live_<kid8>_<rand32>``
tokens by looking up the ``buyer_api_key`` row, argon2id verifying, and
attaching ``(buyer_pk, buyer_id, tier, kid, scope_json)`` to the request.
Reuses :mod:`radivault_search.auth.buyer_tokens` helpers (cross-package
imports are acceptable per spec §5 C-1 guidance).
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
from radivault_fulfillment.errors import (
    AuthExpired,
    AuthMissing,
    AuthWrongPlane,
    FulfillmentError,
)
from radivault_fulfillment.telemetry import AUTH_FAILURES_TOTAL, CACHE_HIT_TOTAL
from radivault_search.auth.buyer_tokens import (
    constant_time_miss,
    parse_bearer,
    verify_buyer_key,
)
from radivault_search.db.repository import get_key_by_kid

log = logging.getLogger("radivault_fulfillment.auth.buyer")

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

# Paths that require the *gateway* plane — a buyer token hitting any of
# these yields ERR_AUTH_WRONG_PLANE (FR-7).
GATEWAY_PATH_PREFIX = "/v1/gateway/"
# Hospital Dashboard paths — handled by GatewayAuthMiddleware via the shared
# ``auth_token`` table (buyer-portal-demo D-2).
HOSPITAL_PATH_PREFIX = "/v1/hospital/"


class BuyerAuthMiddleware(BaseHTTPMiddleware):
    """Resolve a buyer Bearer key on the buyer-facing paths only."""

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
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/static/"):
            return await call_next(request)
        if path.startswith(GATEWAY_PATH_PREFIX) or path.startswith(HOSPITAL_PATH_PREFIX):
            # Gateway / Hospital Dashboard plane — skip (GatewayAuthMiddleware handles both).
            return await call_next(request)

        try:
            self._authenticate(request)
        except CentralError as exc:
            return _envelope_response(exc, request)
        return await call_next(request)

    def _authenticate(self, request: Request) -> None:
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="missing").inc()
            raise AuthMissing()
        bearer = auth.removeprefix("Bearer ").strip()

        # Wrong-plane detection: gateway tokens are plain ULIDs/opaque strings,
        # not rv_live/rv_test. The simple rule — buyer plane requires an
        # rv_* prefix. A gateway-token-looking value here is wrong-plane.
        if not (bearer.startswith("rv_live_") or bearer.startswith("rv_test_")):
            AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="wrong_plane").inc()
            raise AuthWrongPlane()

        parsed = parse_bearer(bearer, allow_test_prefix=self._allow_test)
        if parsed is None:
            AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="format").inc()
            raise AuthExpired(detail="API key format invalid")
        kid, _prefix = parsed

        cached = self._cache_get(kid)
        if cached is not None:
            CACHE_HIT_TOTAL.labels(cache_layer="auth_buyer").inc()
            request.state.buyer_pk = cached["buyer_pk"]
            request.state.buyer_id = cached["buyer_id"]
            request.state.tier = cached["tier"]
            request.state.kid = kid
            request.state.scope_json = cached.get("scope_json") or {}
            return

        with self._session_factory() as session:
            row = get_key_by_kid(session, kid)
            if row is None:
                AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="kid_not_found").inc()
                constant_time_miss(bearer)
                raise AuthExpired(detail="key not found")
            if row.revoked_at is not None:
                AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="revoked").inc()
                raise AuthExpired(detail="key revoked")
            if row.expires_at is not None and row.expires_at < datetime.now(tz=UTC):
                AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="expired").inc()
                raise AuthExpired(detail="key expired")
            if not verify_buyer_key(bearer, row.token_hash):
                AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="hash_mismatch").inc()
                raise AuthExpired(detail="key hash mismatch")
            buyer = row.buyer
            if buyer is None or not buyer.active:
                AUTH_FAILURES_TOTAL.labels(plane="buyer", reason="buyer_inactive").inc()
                raise AuthExpired(detail="buyer inactive")

            ctx = {
                "buyer_pk": buyer.buyer_pk,
                "buyer_id": buyer.buyer_id,
                "tier": row.tier or buyer.tier,
                "scope_json": _merge_scope(buyer.scope_json, row.scope_json),
            }
            request.state.buyer_pk = ctx["buyer_pk"]
            request.state.buyer_id = ctx["buyer_id"]
            request.state.tier = ctx["tier"]
            request.state.kid = kid
            request.state.scope_json = ctx["scope_json"]

            self._cache_set(kid, ctx)

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
    if not isinstance(exc, FulfillmentError):
        envelope["doc_url"] = f"https://docs.radivault.io/fulfillment/errors/{exc.code}"
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    if exc.code == "ERR_AUTH_MISSING":
        headers["WWW-Authenticate"] = 'Bearer realm="radivault-fulfillment"'
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)


def require_buyer(request: Request) -> tuple[int, str, str, str, dict]:
    """Extract ``(buyer_pk, buyer_id, tier, kid, scope_json)`` from request state."""
    buyer_pk = getattr(request.state, "buyer_pk", None)
    buyer_id = getattr(request.state, "buyer_id", None)
    tier = getattr(request.state, "tier", None)
    kid = getattr(request.state, "kid", None)
    scope_json = getattr(request.state, "scope_json", {}) or {}
    if buyer_pk is None or buyer_id is None or tier is None or kid is None:
        raise AuthMissing()
    return buyer_pk, buyer_id, tier, kid, scope_json
