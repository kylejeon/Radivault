"""FastAPI routers for radivault_search.

The ``search_router`` / ``facets_router`` / ``hospitals_router`` /
``probes_router`` / ``version_router`` are re-exported for the app factory.
"""

from __future__ import annotations

from radivault_search.routers.facets import router as facets_router
from radivault_search.routers.hospitals import router as hospitals_router
from radivault_search.routers.probes import router as probes_router
from radivault_search.routers.search import router as search_router
from radivault_search.routers.version import router as version_router

__all__ = [
    "facets_router",
    "hospitals_router",
    "probes_router",
    "search_router",
    "version_router",
]
