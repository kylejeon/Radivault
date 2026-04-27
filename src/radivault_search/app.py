"""FastAPI application factory for radivault_search.

Middleware order (outermost → innermost) matches dev-spec §8.1 flow::

    request-id → auth → rate-limit → routers

When ``testing=True`` an in-memory SQLite engine + fakeredis + the full
metadata (central + search tables) are used so tests don't need external
services.
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
from radivault_search import __version__
from radivault_search.auth.middleware import BuyerAuthMiddleware
from radivault_search.config import Settings
from radivault_search.db.models import Base  # noqa: F401 — registry side-effect
from radivault_search.db.session import get_engine, get_session_factory
from radivault_search.errors import register_exception_handlers
from radivault_search.logging_config import configure_logging
from radivault_search.ratelimit.middleware import RateLimitMiddleware, TierLimits
from radivault_search.preview import preview_router
from radivault_search.preview.storage import LocalPreviewStore, S3PreviewStore
from radivault_search.routers import (
    autocomplete_router,
    facets_router,
    hospitals_router,
    kcd_autocomplete_router,
    probes_router,
    search_router,
    version_router,
)
from radivault_search.telemetry import REGISTRY, init_telemetry

log = logging.getLogger("radivault_search.app")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate/propagate ``X-Request-Id`` as a ULID."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("X-Request-Id") or str(ULID())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", rid)
        return response


def create_app(settings: Settings | None = None, *, testing: bool = False) -> FastAPI:
    """Build a radivault_search FastAPI app wired to its dependencies."""
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
            "radivault_search_starting",
            extra={"event": "service.startup", "version": __version__},
        )
        yield
        log.info("radivault_search_stopping", extra={"event": "service.shutdown"})
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="RadiVault Search",
        version=__version__,
        description="Zone 3 buyer-facing search API — dev-spec-metadata-index.md",
        lifespan=lifespan,
    )

    if testing:
        engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=5, max_overflow=0)
        CentralBase.metadata.create_all(engine)  # includes search tables too
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

    # Preview cache adapter (dev-spec-buyer-browse-preview FR-API-1).
    # In test mode use a temp local FS; production reads MinIO env vars.
    if testing:
        import tempfile

        preview_root = tempfile.mkdtemp(prefix="rv_preview_test_")
        app.state.preview_store = LocalPreviewStore(preview_root)
    else:
        endpoint = os.environ.get("RV_PREVIEW_S3_ENDPOINT")
        bucket = os.environ.get("RV_PREVIEW_S3_BUCKET", "radivault-preview")
        access_key = os.environ.get("RV_PREVIEW_S3_ACCESS_KEY")
        secret_key = os.environ.get("RV_PREVIEW_S3_SECRET_KEY")
        region = os.environ.get("RV_PREVIEW_S3_REGION", "us-east-1")
        # Allow http:// in non-prod envs so MinIO local works without TLS.
        is_prod = settings.app.env == "prod"
        if endpoint:
            app.state.preview_store = S3PreviewStore(
                bucket=bucket,
                region=region,
                endpoint_url=endpoint,
                access_key_id=access_key,
                secret_access_key=secret_key,
                allow_insecure=not is_prod,
            )
        else:
            # Filesystem fallback for dev environments without MinIO.
            preview_root = os.environ.get(
                "RV_PREVIEW_LOCAL_ROOT", "/var/lib/radivault/preview"
            )
            app.state.preview_store = LocalPreviewStore(preview_root)
    app.state.sample_download_daily_limit = int(
        os.environ.get("RV_SAMPLE_DOWNLOAD_DAILY_LIMIT", "1")
    )

    # Middleware — outermost first.
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        tier_preview=TierLimits(
            rpm=settings.rate_limit.tier_preview.rpm,
            daily=settings.rate_limit.tier_preview.daily,
            concurrency=settings.rate_limit.tier_preview.concurrency,
            max_limit_per_page=settings.rate_limit.tier_preview.max_limit_per_page,
        ),
        tier_paid=TierLimits(
            rpm=settings.rate_limit.tier_paid.rpm,
            daily=settings.rate_limit.tier_paid.daily,
            concurrency=settings.rate_limit.tier_paid.concurrency,
            max_limit_per_page=settings.rate_limit.tier_paid.max_limit_per_page,
        ),
        ip_global_per_min=settings.rate_limit.ip_global_per_min,
    )
    app.add_middleware(
        BuyerAuthMiddleware,
        session_factory=session_factory,
        redis_client=redis_client,
        auth_cache_ttl_seconds=settings.redis.auth_cache_ttl_seconds,
        allow_test_prefix=settings.app.env in ("dev", "test", "docker", "stage"),
    )
    app.add_middleware(RequestIdMiddleware)

    # Routers.
    app.include_router(probes_router)
    app.include_router(version_router)
    app.include_router(search_router)
    app.include_router(facets_router)
    app.include_router(hospitals_router)
    app.include_router(kcd_autocomplete_router)
    app.include_router(autocomplete_router)
    app.include_router(preview_router)

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
