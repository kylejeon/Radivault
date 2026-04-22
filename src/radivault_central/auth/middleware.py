"""Bearer-auth middleware and per-request hospital binding (FR-22..FR-27)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from radivault_central.auth.tokens import parse_kid, verify_token
from radivault_central.db.repository import get_hospital_by_pk, get_token_by_kid
from radivault_central.errors import AuthExpired, AuthMissing, CentralError
from radivault_central.telemetry import AUTH_FAILURES

log = logging.getLogger("radivault_central.auth")

# Endpoints that should skip auth — operational probes + version.
PUBLIC_PATHS: frozenset[str] = frozenset(
    {"/healthz", "/readyz", "/v1/version", "/metrics", "/", "/docs", "/openapi.json", "/redoc"}
)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Resolve ``Authorization: Bearer`` into a hospital context.

    On success the request's ``state.hospital_pk`` and ``state.hospital_id``
    are populated. On failure we raise a :class:`CentralError` which the
    standard handler turns into a 401/403 envelope.
    """

    def __init__(self, app: ASGIApp, *, session_factory: Callable) -> None:
        super().__init__(app)
        self._session_factory = session_factory

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
            AUTH_FAILURES.labels(reason="missing").inc()
            raise AuthMissing()
        bearer = auth.removeprefix("Bearer ").strip()
        kid = parse_kid(bearer)
        if kid is None:
            AUTH_FAILURES.labels(reason="missing").inc()
            raise AuthMissing(detail="malformed bearer token")

        with self._session_factory() as session:
            row = get_token_by_kid(session, kid)
            if row is None:
                AUTH_FAILURES.labels(reason="kid_not_found").inc()
                raise AuthExpired(detail="token not found")
            if row.revoked_at is not None:
                AUTH_FAILURES.labels(reason="expired").inc()
                raise AuthExpired(detail="token revoked")
            if row.expires_at is not None and row.expires_at < datetime.now(tz=UTC):
                AUTH_FAILURES.labels(reason="expired").inc()
                raise AuthExpired(detail="token expired")
            if not verify_token(bearer, row.token_hash):
                AUTH_FAILURES.labels(reason="kid_not_found").inc()
                raise AuthExpired(detail="token hash mismatch")
            hospital = get_hospital_by_pk(session, row.hospital_pk)
            if hospital is None or not hospital.active:
                AUTH_FAILURES.labels(reason="mismatch").inc()
                raise AuthExpired(detail="hospital disabled")
            request.state.hospital_pk = hospital.hospital_pk
            request.state.hospital_id = hospital.hospital_id
            request.state.token_kid = row.token_kid
            row.last_used_at = datetime.now(tz=UTC)
            session.commit()


def _envelope_response(exc: CentralError, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    if exc.code == "ERR_AUTH_MISSING":
        headers["WWW-Authenticate"] = 'Bearer realm="central-ingest"'
    return JSONResponse(status_code=exc.status_code, content=exc.to_envelope(rid), headers=headers)


def require_hospital(request: Request) -> tuple[int, str]:
    """Return ``(hospital_pk, hospital_id)`` from a request carried by the middleware."""
    hospital_pk = getattr(request.state, "hospital_pk", None)
    hospital_id = getattr(request.state, "hospital_id", None)
    if hospital_pk is None or hospital_id is None:
        raise AuthMissing()
    return hospital_pk, hospital_id


def ensure_response_mark(response: Response, *, request_id: str) -> Response:
    response.headers.setdefault("X-Request-Id", request_id)
    return response
