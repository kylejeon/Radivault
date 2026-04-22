"""FastAPI application factory for Central Ingest (dev-spec §4.13, FR-22..FR-66).

Middleware order (outermost → innermost) matches design-spec §2 flow::

    request-id → auth → rate-limit → idempotency → route handlers

Errors are caught by a central handler (``radivault_central.errors``) which
renders the bilingual envelope documented in design-spec §2.2.
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

from radivault_central import __version__
from radivault_central.auth.middleware import BearerAuthMiddleware
from radivault_central.config import Settings
from radivault_central.db.models import Base
from radivault_central.db.repository import get_hospital_by_pk
from radivault_central.db.session import get_engine
from radivault_central.errors import register_exception_handlers
from radivault_central.idempotency.middleware import IdempotencyMiddleware
from radivault_central.logging_config import configure_logging
from radivault_central.ratelimit.middleware import RateLimitMiddleware
from radivault_central.routers import (
    anchor_router,
    ingest_router,
    probes_router,
    version_router,
    withdraw_router,
)
from radivault_central.storage.local import LocalFsObjectStore
from radivault_central.storage.s3 import S3ObjectStore
from radivault_central.telemetry import REGISTRY, init_telemetry

log = logging.getLogger("radivault_central.app")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate or propagate an ``X-Request-Id`` header (ULID)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("X-Request-Id") or str(ULID())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", rid)
        return response


def create_app(settings: Settings | None = None, *, testing: bool = False) -> FastAPI:
    """Build a Central Ingest FastAPI app wired to its dependencies.

    When ``testing=True`` an in-memory SQLite engine + fakeredis + local fs
    store are used so unit + integration tests don't require external services.
    """
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
            "central_ingest_starting",
            extra={"event": "service.startup", "version": __version__},
        )
        yield
        log.info("central_ingest_stopping", extra={"event": "service.shutdown"})
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="RadiVault Central Ingest",
        version=__version__,
        description="Zone 2 ingest service — dev-spec-central-ingest.md",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Build infra singletons (engine, redis, store) on app state.
    # ------------------------------------------------------------------
    if testing:
        engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=5, max_overflow=0)
        Base.metadata.create_all(engine)
        import fakeredis

        redis_client = fakeredis.FakeStrictRedis()
        store = LocalFsObjectStore(settings.storage.local_root)
    else:
        engine = get_engine(
            settings.db.dsn,
            pool_size=settings.db.pool_size,
            max_overflow=settings.db.max_overflow,
        )
        import redis as redis_lib  # lazy

        redis_client = redis_lib.Redis.from_url(settings.redis.url, decode_responses=False)
        if settings.storage.provider == "local":
            store = LocalFsObjectStore(settings.storage.local_root)
        else:
            store = S3ObjectStore(
                bucket=settings.storage.bucket,
                region=settings.storage.region,
                endpoint_url=settings.storage.endpoint_url,
                force_path_style=settings.storage.force_path_style,
                access_key_id=settings.storage.access_key_id,
                secret_access_key=settings.storage.secret_access_key,
                kms_key_arn=settings.storage.kms_key_arn,
            )

    from radivault_central.db.session import get_session_factory

    session_factory = get_session_factory(settings.db.dsn)

    app.state.settings = settings
    app.state.engine = engine
    app.state.redis = redis_client
    app.state.object_store = store
    app.state.session_factory = session_factory
    app.state.env = settings.app.env
    app.state.max_manifest_bytes = settings.ops.max_manifest_bytes
    app.state.get_hospital = lambda s, pk: get_hospital_by_pk(s, pk)
    app.state.migrations_state = "head"

    # ------------------------------------------------------------------
    # Middleware — outermost first.
    # ------------------------------------------------------------------
    app.add_middleware(
        IdempotencyMiddleware,
        redis_client=redis_client,
        session_factory=session_factory,
        ttl_seconds=settings.redis.idempotency_ttl_seconds,
    )
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        ingest_per_min=settings.rate_limit.hospital_ingest_per_min,
        ingest_per_hour=settings.rate_limit.hospital_ingest_per_hour,
        anchor_per_min=settings.rate_limit.hospital_anchor_per_min,
        ip_global_per_min=settings.rate_limit.ip_global_per_min,
    )
    app.add_middleware(BearerAuthMiddleware, session_factory=session_factory)
    app.add_middleware(RequestIdMiddleware)

    # ------------------------------------------------------------------
    # Routers.
    # ------------------------------------------------------------------
    app.include_router(probes_router)
    app.include_router(version_router)
    app.include_router(ingest_router)
    app.include_router(anchor_router)
    app.include_router(withdraw_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    register_exception_handlers(app)
    return app


def _create_default() -> FastAPI:
    """Lazy factory used by gunicorn-style ``radivault_central.app:app`` imports."""
    return create_app()


# ``radivault_central.app:app`` is consumed by gunicorn; build lazily.
_app: FastAPI | None = None


def __getattr__(name: str) -> Any:  # pragma: no cover — import sugar
    global _app
    if name == "app":
        if _app is None:
            _app = _create_default()
        return _app
    raise AttributeError(name)
