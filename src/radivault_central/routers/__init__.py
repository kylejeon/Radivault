"""FastAPI routers for Central Ingest."""

from __future__ import annotations

from radivault_central.routers.anchor import router as anchor_router
from radivault_central.routers.ingest import router as ingest_router
from radivault_central.routers.probes import router as probes_router
from radivault_central.routers.version import router as version_router
from radivault_central.routers.withdraw import router as withdraw_router

__all__ = [
    "anchor_router",
    "ingest_router",
    "probes_router",
    "version_router",
    "withdraw_router",
]
