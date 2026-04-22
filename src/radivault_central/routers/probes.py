"""Liveness + readiness probes (dev-spec FR-18 / FR-19, FR-74)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from radivault_central.telemetry import READYZ_CHECKS

log = logging.getLogger("radivault_central.probes")

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """FR-18 — always 200 regardless of dependencies."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    """FR-19 — ping DB + Redis + S3 (+ migrations head)."""
    app_state = request.app.state
    checks: dict[str, str] = {}

    # DB ping
    engine = getattr(app_state, "engine", None)
    if engine is None:
        checks["db"] = "not_configured"
    else:
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            checks["db"] = "ok"
        except Exception as exc:
            log.warning("readyz_db_fail", extra={"event": "readyz.db.fail", "detail": str(exc)})
            checks["db"] = "timeout"

    # Redis ping
    redis_client = getattr(app_state, "redis", None)
    if redis_client is None:
        checks["redis"] = "not_configured"
    else:
        try:
            redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "timeout"

    # Object store head
    store = getattr(app_state, "object_store", None)
    if store is None:
        checks["s3"] = "not_configured"
    else:
        try:
            checks["s3"] = "ok" if store.head_bucket() else "fail"
        except Exception:
            checks["s3"] = "fail"

    # Migrations — if alembic status tracked we'd check here; v0.1 flat head.
    checks["migrations"] = getattr(app_state, "migrations_state", "head")

    for check, value in checks.items():
        READYZ_CHECKS.labels(check=check).set(1.0 if value == "ok" else 0.0)

    ready = all(v in {"ok", "head"} for v in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready, "checks": checks},
    )
