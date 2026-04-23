"""Idempotency middleware for POST endpoints (FR-9/10/47).

Enforced on:
- ``POST /v1/orders``
- ``POST /v1/orders/{id}/cancel``
- ``POST /v1/gateway/transfer-jobs/{id}/progress``
- ``POST /v1/gateway/transfer-jobs/{id}/complete``
- ``POST /v1/gateway/transfer-jobs/{id}/fail``

Redis ``SETNX`` provides the fast-path; the ``order_idempotency_mirror``
table survives Redis TTL expiry (the gateway paths don't need a mirror
row in v0.1 because only orders have a buyer context).
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

from radivault_central.errors import CentralError

from radivault_fulfillment.db.models import OrderIdempotencyMirror
from radivault_fulfillment.errors import (
    FulfillmentError,
    IdempFormat,
    IdempMissing,
    IdempUnavailable,
)

log = logging.getLogger("radivault_fulfillment.idempotency")

IDEMPOTENCY_HEADER = "Idempotency-Key"
_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{16,128}$")


IDEMPOTENT_PATH_RULES = (
    ("POST", re.compile(r"^/v1/orders$")),
    ("POST", re.compile(r"^/v1/orders/[^/]+/cancel$")),
    ("POST", re.compile(r"^/v1/gateway/transfer-jobs/[^/]+/progress$")),
    ("POST", re.compile(r"^/v1/gateway/transfer-jobs/[^/]+/complete$")),
    ("POST", re.compile(r"^/v1/gateway/transfer-jobs/[^/]+/fail$")),
)


class IdempotencyKeyValidator:
    @staticmethod
    def validate(value: str | None) -> str:
        if not value:
            raise IdempMissing()
        key = value.strip()
        if not _PATTERN.match(key):
            raise IdempFormat()
        return key


def _requires_idempotency(request: Request) -> bool:
    method = request.method.upper()
    path = request.url.path
    return any(
        method == m and pattern.match(path)
        for m, pattern in IDEMPOTENT_PATH_RULES
    )


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Enforce Idempotency-Key on all fulfilment POSTs that need it."""

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
        if not _requires_idempotency(request):
            return await call_next(request)

        key_header = request.headers.get(IDEMPOTENCY_HEADER)
        try:
            key = IdempotencyKeyValidator.validate(key_header)
        except CentralError as exc:
            return _envelope_response(exc, request)

        # Scope: buyer POSTs key by buyer_pk, gateway POSTs by hospital_pk.
        scope_owner = (
            getattr(request.state, "buyer_pk", None)
            or getattr(request.state, "hospital_pk", None)
        )
        if scope_owner is None:
            # Auth middleware must have failed earlier; let it surface.
            return await call_next(request)
        scope_type = (
            "buyer" if getattr(request.state, "buyer_pk", None) else "gw"
        )

        redis_key = f"idem:ff:{scope_type}:{scope_owner}:{key}"
        cached = None
        if self._redis is not None:
            try:
                cached = self._redis.get(redis_key)
            except Exception as exc:
                log.warning(
                    "redis_get_fail",
                    extra={"event": "redis.error", "detail": str(exc)},
                )
                return _envelope_response(IdempUnavailable(), request)

        if cached is not None:
            try:
                payload = json.loads(
                    cached.decode("utf-8") if isinstance(cached, bytes) else cached
                )
                body_text = payload.get("body", "")
                status = int(payload.get("status", 200))
            except Exception:
                return _envelope_response(IdempUnavailable(), request)
            headers = {
                "Idempotency-Replayed": "true",
                "Content-Type": "application/json",
            }
            return JSONResponse(
                content=json.loads(body_text) if body_text.strip().startswith("{") else {},
                status_code=status,
                headers=headers,
            )

        response = await call_next(request)
        body = b""
        try:
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body += chunk
        except AttributeError:
            body = getattr(response, "body", b"") or b""

        if 200 <= response.status_code < 300 and self._redis is not None:
            envelope = {
                "status": response.status_code,
                "body": body.decode("utf-8", errors="replace"),
            }
            payload_str = json.dumps(envelope)
            try:
                self._redis.set(redis_key, payload_str, ex=self._ttl, nx=True)
            except Exception as exc:  # pragma: no cover
                log.warning(
                    "redis_set_fail",
                    extra={"event": "redis.error", "detail": str(exc)},
                )
            if scope_type == "buyer":
                with self._session_factory() as session:
                    existing = session.get(
                        OrderIdempotencyMirror, (key, int(scope_owner))
                    )
                    if existing is None:
                        session.add(
                            OrderIdempotencyMirror(
                                key=key,
                                buyer_pk=int(scope_owner),
                                response_sha256=hashlib.sha256(body).digest(),
                                response_status_code=response.status_code,
                                response_body=body.decode("utf-8", errors="replace"),
                            )
                        )
                        session.commit()

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


def _envelope_response(exc: CentralError, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    envelope = exc.to_envelope(rid)
    if not isinstance(exc, FulfillmentError):
        envelope["doc_url"] = f"https://docs.radivault.io/fulfillment/errors/{exc.code}"
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)


__all__ = ["IdempotencyKeyValidator", "IdempotencyMiddleware"]
