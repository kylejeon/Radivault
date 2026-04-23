"""Gateway-plane auth middleware — reuses central-ingest auth_token.

FR-4/5/7: validates ``Authorization: Bearer <token>`` against
``auth_token`` rows (argon2id hash verification), attaches
``(hospital_pk, hospital_id, token_kid)`` to the request. Only active on
``/v1/gateway/*`` paths (other paths fall through to BuyerAuthMiddleware).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from radivault_central.auth.tokens import parse_kid, verify_token
from radivault_central.db.repository import get_hospital_by_pk, get_token_by_kid
from radivault_central.errors import CentralError
from radivault_fulfillment.errors import (
    AuthExpired,
    AuthMissing,
    AuthWrongPlane,
    FulfillmentError,
)
from radivault_fulfillment.telemetry import AUTH_FAILURES_TOTAL

log = logging.getLogger("radivault_fulfillment.auth.gateway")


GATEWAY_PATH_PREFIX = "/v1/gateway/"
# Hospital Dashboard endpoints (buyer-portal-demo D-2) reuse the same
# central-ingest ``auth_token`` for now — BFF proxies the hospital bearer
# through to order-fulfillment. The v0.1.5 plan is a dedicated hospital
# admin SSO path.
HOSPITAL_PATH_PREFIX = "/v1/hospital/"


def _is_hospital_auth_path(path: str) -> bool:
    return path.startswith(GATEWAY_PATH_PREFIX) or path.startswith(HOSPITAL_PATH_PREFIX)


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    """Resolve a hospital-plane Bearer on ``/v1/gateway/*`` + ``/v1/hospital/*``."""

    def __init__(self, app: ASGIApp, *, session_factory: Callable) -> None:
        super().__init__(app)
        self._session_factory = session_factory

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not _is_hospital_auth_path(request.url.path):
            return await call_next(request)
        try:
            self._authenticate(request)
        except CentralError as exc:
            return _envelope_response(exc, request)
        return await call_next(request)

    def _authenticate(self, request: Request) -> None:
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="missing").inc()
            raise AuthMissing()
        bearer = auth.removeprefix("Bearer ").strip()

        # Wrong-plane detection — a buyer rv_live/rv_test token here is an
        # attempt to cross planes.
        if bearer.startswith("rv_live_") or bearer.startswith("rv_test_"):
            AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="wrong_plane").inc()
            raise AuthWrongPlane()

        kid = parse_kid(bearer)
        if kid is None:
            AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="format").inc()
            raise AuthMissing(detail="malformed bearer token")

        with self._session_factory() as session:
            row = get_token_by_kid(session, kid)
            if row is None:
                AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="kid_not_found").inc()
                raise AuthExpired(detail="token not found")
            if row.revoked_at is not None:
                AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="revoked").inc()
                raise AuthExpired(detail="token revoked")
            if row.expires_at is not None and row.expires_at < datetime.now(tz=UTC):
                AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="expired").inc()
                raise AuthExpired(detail="token expired")
            if not verify_token(bearer, row.token_hash):
                AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="hash_mismatch").inc()
                raise AuthExpired(detail="token hash mismatch")
            hospital = get_hospital_by_pk(session, row.hospital_pk)
            if hospital is None or not hospital.active:
                AUTH_FAILURES_TOTAL.labels(plane="gateway", reason="hospital_inactive").inc()
                raise AuthExpired(detail="hospital disabled")
            request.state.hospital_pk = hospital.hospital_pk
            request.state.hospital_id = hospital.hospital_id
            request.state.token_kid = row.token_kid
            request.state.gateway_id = f"gw_{hospital.hospital_id}"


def _envelope_response(exc: CentralError, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    envelope = exc.to_envelope(rid)
    if not isinstance(exc, FulfillmentError):
        envelope["doc_url"] = f"https://docs.radivault.io/fulfillment/errors/{exc.code}"
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    if exc.code == "ERR_AUTH_MISSING":
        headers["WWW-Authenticate"] = 'Bearer realm="radivault-fulfillment-gateway"'
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)


def require_gateway(request: Request) -> tuple[int, str, str]:
    """Return ``(hospital_pk, hospital_id, gateway_id)`` from an authed request."""
    hospital_pk = getattr(request.state, "hospital_pk", None)
    hospital_id = getattr(request.state, "hospital_id", None)
    gateway_id = getattr(request.state, "gateway_id", None)
    if hospital_pk is None or hospital_id is None or gateway_id is None:
        raise AuthMissing()
    return hospital_pk, hospital_id, gateway_id
