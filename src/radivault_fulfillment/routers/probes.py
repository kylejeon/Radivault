"""Operational probes (dev-spec §7.10)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text
from starlette.responses import JSONResponse

router = APIRouter(tags=["probes"])


@router.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/readyz", include_in_schema=False)
def readyz(request: Request) -> JSONResponse:
    """Check PG + Redis + migrations state (S3 HEAD is optional; §11 Q6)."""
    checks: dict[str, str] = {}
    overall_ok = True

    # PG ping.
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        checks["db"] = "no_engine"
        overall_ok = False
    else:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception as exc:
            checks["db"] = f"fail: {exc.__class__.__name__}"
            overall_ok = False

    # Redis ping (optional; degraded but not failing).
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        checks["redis"] = "skipped"
    else:
        try:
            redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "fail"
            overall_ok = False

    checks["migrations"] = getattr(request.app.state, "migrations_state", "unknown")

    status = 200 if overall_ok else 503
    return JSONResponse(
        {"status": "ok" if overall_ok else "degraded", "checks": checks}, status_code=status
    )
