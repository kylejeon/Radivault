"""Uvicorn/gunicorn entrypoint for Central Ingest (dev-spec FR-66)."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Start the Central Ingest ASGI app with uvicorn.

    Production deployments should use ``gunicorn radivault_central.app:app``
    with ``-k uvicorn.workers.UvicornWorker`` (see FR-66). This entrypoint is
    the simple dev/prod single-command fallback.
    """
    import uvicorn

    host = os.environ.get("RADIVAULT_HOST", "0.0.0.0")
    port = int(os.environ.get("RADIVAULT_PORT", "8000"))
    log_level = os.environ.get("RV_CENTRAL_LOG_LEVEL", "info").lower()

    uvicorn.run(
        "radivault_central.app:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,  # our JSON logger handles access logs
        factory=False,
    )


if __name__ == "__main__":
    main()
    sys.exit(0)
