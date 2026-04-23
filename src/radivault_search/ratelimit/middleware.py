"""Per-buyer rate-limit + daily quota + concurrency cap (dev-spec §4.2).

Uses Redis-backed fixed-window counters scoped by ``(buyer_pk, window)``.

Failure modes:

- Redis unavailable → the middleware returns ``503 ERR_IDEMP_UNAVAILABLE``
  (shared Redis backend with central-ingest; FR-14).
- Per-minute limit exceeded → ``429 ERR_RATE_LIMITED`` (+ Retry-After).
- Daily quota exhausted → ``429 ERR_BUYER_QUOTA``.
- Per-buyer concurrency cap exceeded → ``429 ERR_BUYER_CONCURRENCY``.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from radivault_central.errors import CentralError
from radivault_search.errors import (
    BuyerConcurrency,
    BuyerQuota,
    IdempUnavailable,
    RateLimited,
    SearchError,
)
from radivault_search.telemetry import RATE_LIMITED_TOTAL

log = logging.getLogger("radivault_search.ratelimit")


# Only these endpoints are subject to per-buyer rate-limit. Probes/version/
# metrics bypass.
PROTECTED_PREFIXES = ("/v1/search/",)


@dataclass
class TierLimits:
    rpm: int = 20
    daily: int = 100
    concurrency: int = 3


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-minute + per-day counters + concurrency cap."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        redis_client,
        tier_preview: TierLimits,
        tier_paid: TierLimits,
        ip_global_per_min: int = 300,
    ) -> None:
        super().__init__(app)
        self._redis = redis_client
        self._tier_preview = tier_preview
        self._tier_paid = tier_paid
        self._ip_limit = ip_global_per_min

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]):
        path = request.url.path
        if not any(path.startswith(p) for p in PROTECTED_PREFIXES):
            return await call_next(request)

        buyer_pk = getattr(request.state, "buyer_pk", None)
        if buyer_pk is None:
            # Not authed (shouldn't reach here if auth middleware precedes),
            # skip rate-limit.
            return await call_next(request)
        tier: str = getattr(request.state, "tier", "preview") or "preview"
        limits = self._tier_paid if tier == "paid" else self._tier_preview

        # 1. per-minute
        try:
            if self._over_limit(f"search:rl:minute:{buyer_pk}", window=60, limit=limits.rpm):
                RATE_LIMITED_TOTAL.labels(tier=tier, reason="rpm").inc()
                exc = RateLimited(
                    detail=f"rate limit {limits.rpm}/min exceeded",
                    retry_after=60,
                )
                return _envelope_response(exc, request)
        except RedisDown:
            return _envelope_response(IdempUnavailable(), request)

        # 2. daily quota
        try:
            day = time.strftime("%Y%m%d", time.gmtime())
            if self._over_limit(
                f"search:rl:daily:{buyer_pk}:{day}",
                window=60 * 60 * 26,  # ≥ 24h so the window survives clock skew
                limit=limits.daily,
            ):
                RATE_LIMITED_TOTAL.labels(tier=tier, reason="daily").inc()
                # Compute retry_after until UTC midnight.
                now = time.time()
                retry_after = int(((int(now) // 86400) + 1) * 86400 - now)
                exc = BuyerQuota(
                    detail=(f"daily quota exhausted: {limits.daily}/{limits.daily} requests used"),
                    retry_after=max(retry_after, 60),
                )
                return _envelope_response(exc, request)
        except RedisDown:
            return _envelope_response(IdempUnavailable(), request)

        # 3. concurrency cap — INCR/DECR around call_next in a finally block.
        key_inflight = f"search:inflight:{buyer_pk}"
        try:
            try:
                count = int(self._redis.incr(key_inflight))
                self._redis.expire(key_inflight, 60)
            except Exception as exc:
                log.warning("redis unavailable: %s", exc)
                return _envelope_response(IdempUnavailable(), request)
            if count > limits.concurrency:
                RATE_LIMITED_TOTAL.labels(tier=tier, reason="concurrency").inc()
                excc = BuyerConcurrency(
                    detail=(f"per-buyer concurrency cap {limits.concurrency} reached")
                )
                return _envelope_response(excc, request)
            return await call_next(request)
        finally:
            with contextlib.suppress(Exception):
                self._redis.decr(key_inflight)

    # ------------------------------------------------------------------
    def _over_limit(self, key: str, *, window: int, limit: int) -> bool:
        try:
            count = int(self._redis.incr(key))
            if count == 1:
                self._redis.expire(key, window)
            return count > limit
        except Exception as exc:  # Treat any error as Redis-down.
            raise RedisDown(str(exc)) from exc


class RedisDown(Exception):
    """Raised internally when Redis ops fail — mapped to 503."""


def _envelope_response(exc: CentralError, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    envelope = exc.to_envelope(rid)
    if not isinstance(exc, SearchError):
        envelope["doc_url"] = f"https://docs.radivault.io/search/errors/{exc.code}"
    headers: dict[str, str] = {"X-Request-Id": rid}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)
