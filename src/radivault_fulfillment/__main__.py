"""Uvicorn/gunicorn entrypoint for radivault_fulfillment (dev-spec §3.1 #1)."""

from __future__ import annotations

import os


def main() -> None:
    """Start the Fulfillment ASGI app with uvicorn.

    Production deployments should use gunicorn with UvicornWorker. Default
    port is 8002 (central=8000, search=8001).
    """
    import uvicorn

    host = os.environ.get("RADIVAULT_FULFILLMENT_HOST", "0.0.0.0")
    port = int(os.environ.get("RADIVAULT_FULFILLMENT_PORT", "8002"))
    log_level = os.environ.get("RV_FULFILLMENT_LOG_LEVEL", "info").lower()

    uvicorn.run(
        "radivault_fulfillment.app:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
        factory=False,
    )


if __name__ == "__main__":
    main()
