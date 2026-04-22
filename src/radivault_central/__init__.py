"""RadiVault Central Ingest service — Zone 2 entry point.

See ``docs/specs/dev-spec-central-ingest.md`` (75 FRs, 36 AC) for the canonical
contract. This package exposes:

- ``radivault_central.app`` — FastAPI application factory (:func:`create_app`).
- ``radivault_central.config`` — pydantic Settings loaded from env / YAML.
- ``radivault_central.__main__`` — uvicorn/gunicorn entrypoint.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
