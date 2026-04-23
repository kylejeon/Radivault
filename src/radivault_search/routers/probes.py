"""Liveness + readiness probes (dev-spec §7.5)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("radivault_search.probes")

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Always 200 regardless of dependencies."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    """PG ping + Redis ping + alembic_state."""
    app_state = request.app.state
    checks: dict[str, str] = {}

    engine = getattr(app_state, "engine", None)
    if engine is None:
        checks["db"] = "not_configured"
    else:
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            checks["db"] = "ok"
        except Exception as exc:
            log.warning("readyz_db_fail", extra={"detail": str(exc)})
            checks["db"] = "timeout"

    redis_client = getattr(app_state, "redis", None)
    if redis_client is None:
        checks["redis"] = "not_configured"
    else:
        try:
            redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "timeout"

    checks["migrations"] = getattr(app_state, "migrations_state", "head")

    ready = all(v in {"ok", "head"} for v in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready, "checks": checks},
    )
