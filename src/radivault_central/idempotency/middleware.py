"""Idempotency middleware (dev-spec FR-28..FR-33).

Uses Redis ``SETNX`` for the first-see lock and mirrors finalised responses to
the ``ingest_idempotency_mirror`` table so audit can survive Redis TTL expiry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from radivault_central.db.repository import (
    get_idempotency_mirror,
    upsert_idempotency_mirror,
)
from radivault_central.errors import (
    CentralError,
    IdempFormat,
    IdempMissing,
    IdempUnavailable,
)
from radivault_central.telemetry import IDEMPOTENCY_DEDUP

log = logging.getLogger("radivault_central.idempotency")

IDEMPOTENCY_HEADER = "Idempotency-Key"
_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{16,128}$")

# Endpoints that require idempotency keys.
IDEMPOTENT_PATHS = (
    "/v1/ingest/studies",
    "/v1/audit/anchor",
)


class IdempotencyKeyValidator:
    """Small helper that exposes header parsing so CLI / tests can reuse it."""

    @staticmethod
    def validate(value: str | None) -> str:
        if not value:
            raise IdempMissing()
        key = value.strip()
        if not _PATTERN.match(key):
            raise IdempFormat()
        return key


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Enforce ``Idempotency-Key``, short-circuit replays."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        redis_client,
        session_factory: Callable,
        ttl_seconds: int = 86400,
    ) -> None:
        super().__init__(app)
        self._redis = redis_client
        self._session_factory = session_factory
        self._ttl = ttl_seconds

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method.upper() != "POST" or not any(
            request.url.path == p for p in IDEMPOTENT_PATHS
        ):
            return await call_next(request)

        key_header = request.headers.get(IDEMPOTENCY_HEADER)
        try:
            key = IdempotencyKeyValidator.validate(key_header)
        except CentralError as exc:
            return _envelope_response(exc, request)
        hospital_pk = getattr(request.state, "hospital_pk", None)
        if hospital_pk is None:
            # Auth middleware must have failed earlier; respect it.
            return await call_next(request)

        redis_key = f"idem:{hospital_pk}:{key}"
        try:
            cached = self._redis.get(redis_key)
        except Exception as exc:  # redis.ConnectionError / TimeoutError etc
            log.warning("redis_get_fail", extra={"event": "redis.error", "detail": str(exc)})
            return _envelope_response(IdempUnavailable(), request)

        if cached is not None:
            try:
                return self._replay(cached, hospital_pk, request, key)
            except CentralError as exc:
                return _envelope_response(exc, request)

        response = await call_next(request)
        body = b""
        try:
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body += chunk
        except AttributeError:
            body = getattr(response, "body", b"") or b""

        # Only remember 2xx responses.
        if 200 <= response.status_code < 300:
            envelope = {
                "status": response.status_code,
                "body": body.decode("utf-8", errors="replace"),
            }
            payload = json.dumps(envelope)
            try:
                self._redis.set(redis_key, payload, ex=self._ttl, nx=True)
            except Exception as exc:  # pragma: no cover - optional tolerance
                log.warning("redis_set_fail", extra={"event": "redis.error", "detail": str(exc)})
            with self._session_factory() as session:
                upsert_idempotency_mirror(
                    session,
                    key=key,
                    hospital_pk=hospital_pk,
                    response_sha256=hashlib.sha256(body).digest(),
                    response_status_code=response.status_code,
                    response_body=body.decode("utf-8", errors="replace"),
                )
                session.commit()
            IDEMPOTENCY_DEDUP.labels(hospital_id=request.state.hospital_id, result="miss").inc()

        # Rebuild the response with the consumed body.
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _replay(
        self,
        cached: bytes | str,
        hospital_pk: int,
        request: Request,
        key: str,
    ) -> JSONResponse:
        payload_raw = cached.decode("utf-8") if isinstance(cached, bytes) else cached
        try:
            payload = json.loads(payload_raw)
            body_text = payload.get("body", "")
            status = int(payload.get("status", 200))
        except Exception:  # pragma: no cover — corrupt cache entry
            # Fall back to the DB mirror.
            with self._session_factory() as session:
                mirror = get_idempotency_mirror(session, key=key, hospital_pk=hospital_pk)
            if mirror is None:
                raise IdempUnavailable()  # noqa: B904
            body_text = mirror.response_body or ""
            status = mirror.response_status_code

        headers = {
            "Idempotency-Replayed": "true",
            "Content-Type": "application/json",
        }
        IDEMPOTENCY_DEDUP.labels(hospital_id=request.state.hospital_id, result="hit").inc()
        return JSONResponse(
            content=json.loads(body_text) if body_text.strip().startswith("{") else {},
            status_code=status,
            headers=headers,
        )


def _envelope_response(exc: CentralError, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(status_code=exc.status_code, content=exc.to_envelope(rid), headers=headers)
