"""FastAPI router exports."""

from __future__ import annotations

from radivault_fulfillment.routers.buyer_orders import router as buyer_orders_router
from radivault_fulfillment.routers.gateway_jobs import router as gateway_jobs_router
from radivault_fulfillment.routers.probes import router as probes_router
from radivault_fulfillment.routers.version import router as version_router

__all__ = [
    "buyer_orders_router",
    "gateway_jobs_router",
    "probes_router",
    "version_router",
]
