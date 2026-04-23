"""RadiVault Search — buyer-facing metadata search API (Zone 3).

See ``docs/specs/dev-spec-metadata-index.md`` (77 FRs, 34 AC) for the canonical
contract. This package exposes:

- ``radivault_search.app`` — FastAPI application factory (:func:`create_app`).
- ``radivault_search.config`` — pydantic/dataclass Settings.
- ``radivault_search.__main__`` — uvicorn/gunicorn entrypoint.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
