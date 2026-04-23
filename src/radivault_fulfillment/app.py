"""FastAPI application factory for radivault_fulfillment.

Middleware order (outermost → innermost) follows dev-spec §8.1:

    request-id → gateway-auth → buyer-auth → url-mint-rate-limit → idempotency → routers

When ``testing=True`` an in-memory SQLite engine + fakeredis are used so
the full suite runs without external services.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from ulid import ULID

from radivault_central.db.models import Base as CentralBase
from radivault_fulfillment import __version__
from radivault_fulfillment.auth.buyer import BuyerAuthMiddleware
from radivault_fulfillment.auth.gateway import GatewayAuthMiddleware
from radivault_fulfillment.config import Settings
from radivault_fulfillment.db import models as _fulfillment_models  # noqa: F401 — registry side-effect
from radivault_fulfillment.db.session import get_engine, get_session_factory
from radivault_fulfillment.download.presigned import PresignedSigner
from radivault_fulfillment.errors import register_exception_handlers
from radivault_fulfillment.idempotency.middleware import IdempotencyMiddleware
from radivault_fulfillment.logging_config import configure_logging
from radivault_fulfillment.ratelimit.middleware import UrlMintRateLimitMiddleware
from radivault_fulfillment.routers import (
    buyer_orders_router,
    gateway_jobs_router,
    probes_router,
    version_router,
)
from radivault_fulfillment.telemetry import REGISTRY, init_telemetry

log = logging.getLogger("radivault_fulfillment.app")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("X-Request-Id") or str(ULID())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", rid)
        return response


def create_app(settings: Settings | None = None, *, testing: bool = False) -> FastAPI:
    settings = settings or Settings.load()
    configure_logging(
        level=settings.observability.log_level,
        json_logs=settings.observability.json_logs,
    )
    init_telemetry(
        version=__version__,
        git_sha=os.environ.get("RADIVAULT_GIT_SHA", "unknown"),
        python_version=".".join(str(s) for s in sys.version_info[:3]),
        otlp_endpoint=settings.observability.otlp_endpoint,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info(
            "radivault_fulfillment_starting",
            extra={"event": "service.startup", "version": __version__},
        )
        yield
        log.info(
            "radivault_fulfillment_stopping", extra={"event": "service.shutdown"}
        )
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="RadiVault Order Fulfillment",
        version=__version__,
        description="Zone 2 buyer orders + transfer-job orchestration",
        lifespan=lifespan,
    )

    if testing:
        engine = get_engine(
            "sqlite+pysqlite:///:memory:", pool_size=5, max_overflow=0
        )
        CentralBase.metadata.create_all(engine)
        import fakeredis

        redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    else:
        engine = get_engine(
            settings.db.dsn,
            pool_size=settings.db.pool_size,
            max_overflow=settings.db.max_overflow,
        )
        import redis as redis_lib  # lazy

        redis_client = redis_lib.Redis.from_url(settings.redis.url, decode_responses=True)

    session_factory = get_session_factory(settings.db.dsn)

    app.state.settings = settings
    app.state.engine = engine
    app.state.redis = redis_client
    app.state.session_factory = session_factory
    app.state.env = settings.app.env
    app.state.migrations_state = "head"
    app.state.presigned_signer = PresignedSigner(
        bucket=settings.storage.bucket,
        region=settings.storage.region,
        endpoint_url=settings.storage.endpoint_url,
    )

    # Middleware stack — outermost first.
    app.add_middleware(
        IdempotencyMiddleware,
        redis_client=redis_client,
        session_factory=session_factory,
        ttl_seconds=settings.redis.idempotency_ttl_seconds,
    )
    app.add_middleware(
        UrlMintRateLimitMiddleware,
        redis_client=redis_client,
        per_5s=settings.download.rate_limit_mint_per_5s,
        burst=settings.download.rate_limit_mint_burst,
    )
    app.add_middleware(
        BuyerAuthMiddleware,
        session_factory=session_factory,
        redis_client=redis_client,
        auth_cache_ttl_seconds=settings.redis.auth_cache_ttl_seconds,
        allow_test_prefix=settings.app.env in ("dev", "test", "docker", "stage"),
    )
    app.add_middleware(
        GatewayAuthMiddleware,
        session_factory=session_factory,
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(probes_router)
    app.include_router(version_router)
    app.include_router(buyer_orders_router)
    app.include_router(gateway_jobs_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    register_exception_handlers(app)
    return app


_app: FastAPI | None = None


def __getattr__(name: str) -> Any:  # pragma: no cover — import sugar
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)
