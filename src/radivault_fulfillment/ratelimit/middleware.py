"""Lightweight per-buyer rate limits for URL mint (FR-67).

The heavy-lifting rate limits (per-tier rpm / daily quotas) rely on the
metadata-index sibling which tracks cross-service counters. For v0.1 we
implement the endpoint-scoped rules the dev-spec calls out — chiefly
``POST /v1/orders/{id}/download-urls`` rate limit (1 req/5s, burst 10).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from radivault_fulfillment.errors import UrlMintRate
from radivault_fulfillment.telemetry import URL_MINT_RATE_LIMITED_TOTAL

URL_MINT_PATH_FRAGMENT = "/download-urls"


class UrlMintRateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket on Redis key ``urlmint_rate:{buyer_pk}``."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        redis_client,
        per_5s: int = 1,
        burst: int = 10,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        super().__init__(app)
        self._redis = redis_client
        self._per_5s = max(1, per_5s)
        self._burst = max(1, burst)
        self._time = time_fn

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not (
            request.method == "POST"
            and request.url.path.endswith(URL_MINT_PATH_FRAGMENT)
        ):
            return await call_next(request)

        buyer_pk = getattr(request.state, "buyer_pk", None)
        if buyer_pk is None:
            return await call_next(request)

        if self._redis is None or not self._blocking(buyer_pk):
            return await call_next(request)
        # Rate-limit triggered.
        URL_MINT_RATE_LIMITED_TOTAL.inc()
        exc = UrlMintRate()
        rid = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_envelope(rid),
            headers={"X-Request-Id": rid, "Retry-After": str(exc.retry_after or 5)},
        )

    def _blocking(self, buyer_pk: int) -> bool:
        """Return True when the call should be rate-limited."""
        key = f"urlmint_rate:{buyer_pk}"
        now_ms = int(self._time() * 1000)
        window_ms = 5_000
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, now_ms - window_ms)
            pipe.zadd(key, {str(now_ms): now_ms})
            pipe.zcard(key)
            pipe.expire(key, 30)
            _, _, count, _ = pipe.execute()
            return int(count) > self._burst
        except Exception:
            # Fail open if Redis misbehaves — the spec prefers availability
            # over throttling for this particular limit.
            return False


__all__ = ["UrlMintRateLimitMiddleware"]
