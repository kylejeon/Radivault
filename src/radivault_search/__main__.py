"""Uvicorn/gunicorn entrypoint for radivault_search (dev-spec FR-60)."""

from __future__ import annotations

import os


def main() -> None:
    """Start the Search ASGI app with uvicorn.

    Production deployments should use ``gunicorn radivault_search.app:app``
    with ``-k uvicorn.workers.UvicornWorker``. This entrypoint is the simple
    dev/prod single-command fallback. Default port is 8001 (central is 8000).
    """
    import uvicorn

    host = os.environ.get("RADIVAULT_SEARCH_HOST", "0.0.0.0")
    port = int(os.environ.get("RADIVAULT_SEARCH_PORT", "8001"))
    log_level = os.environ.get("RV_SEARCH_LOG_LEVEL", "info").lower()

    uvicorn.run(
        "radivault_search.app:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
        factory=False,
    )


if __name__ == "__main__":
    main()
