"""Lightweight per-hospital rate limiter (dev-spec §4.7).

We implement rate limiting with a Redis-backed sliding window rather than
pulling in ``slowapi``'s decorator machinery. ``slowapi`` is declared as a
dependency because its ``limits`` library is used directly for window math, but
the middleware binding is our own so we can use the auth-provided hospital
context (slowapi's default keyfunc is by-IP which isn't enough).

If Redis is unavailable we fail **open** for this middleware — rate limiting is
a best-effort signal; the idempotency middleware will already catch hard Redis
outages with a 503.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from radivault_central.errors import CentralError, RateLimited
from radivault_central.telemetry import RATE_LIMIT_HITS

log = logging.getLogger("radivault_central.ratelimit")


def hospital_key(request: Request) -> str:
    """Key function: prefer hospital_pk, fall back to client IP."""
    hpk = getattr(request.state, "hospital_pk", None)
    if hpk is not None:
        return f"hospital:{hpk}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window Redis rate limiter scoped by (hospital, endpoint)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        redis_client,
        ingest_per_min: int = 60,
        ingest_per_hour: int = 2000,
        anchor_per_min: int = 6,
        ip_global_per_min: int = 300,
    ) -> None:
        super().__init__(app)
        self._redis = redis_client
        self._ingest_min = ingest_per_min
        self._ingest_hour = ingest_per_hour
        self._anchor_min = anchor_per_min
        self._ip_min = ip_global_per_min

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable]
    ):
        path = request.url.path
        scope = None
        window: int | None = None

        if path == "/v1/ingest/studies" and request.method.upper() == "POST":
            if self._over_limit(request, scope="ingest_min", window=60, limit=self._ingest_min):
                scope = "per_min"
                window = 60
            elif self._over_limit(
                request, scope="ingest_hour", window=3600, limit=self._ingest_hour
            ):
                scope = "per_hour"
                window = 3600
        elif (
            path == "/v1/audit/anchor"
            and request.method.upper() == "POST"
            and self._over_limit(
                request, scope="anchor_min", window=60, limit=self._anchor_min
            )
        ):
            scope = "per_min"
            window = 60

        if scope is not None:
            hospital_id = getattr(request.state, "hospital_id", "unknown") or "unknown"
            RATE_LIMIT_HITS.labels(hospital_id=hospital_id, scope=scope).inc()
            exc = RateLimited(
                detail=f"{path} rate limit exceeded (scope={scope})",
                retry_after=window or 60,
            )
            return _envelope_response(exc, request)
        return await call_next(request)

    def _over_limit(
        self,
        request: Request,
        *,
        scope: str,
        window: int,
        limit: int,
    ) -> bool:
        bucket = int(time.time() // window)
        key_prefix = hospital_key(request)
        rkey = f"rl:{scope}:{key_prefix}:{bucket}"
        try:
            count = self._redis.incr(rkey)
            if count == 1:
                self._redis.expire(rkey, window)
        except Exception as exc:  # redis fail-open
            log.warning("ratelimit_redis_fail", extra={"event": "redis.error", "detail": str(exc)})
            return False
        return int(count) > limit


def _envelope_response(exc: CentralError, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.status_code, content=exc.to_envelope(rid), headers=headers
    )
