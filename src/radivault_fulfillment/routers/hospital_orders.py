"""Hospital-scoped order stream (dev-spec buyer-portal-demo D-2 part 2).

The Hospital Dashboard B-5 tile needs a view of recent orders that consumed
studies from the authenticated hospital, without leaking buyer identity. This
router exposes one endpoint:

``GET /v1/hospital/me/orders?limit=10``

Auth is the hospital bearer (central-ingest ``auth_token``) already resolved
by :class:`GatewayAuthMiddleware` — the middleware was extended to recognise
``/v1/hospital/*`` paths in the same commit.

PHI / scope posture
-------------------
* Scope: SELECT is restricted to orders that have at least one ``order_item``
  with ``hospital_pk == request hospital``. The buyer's identity
  (``buyer_pk``, ``buyer_id``, ``kid``) is never included in the response.
* PHI: only opaque ``order_id`` (masked to 8 chars), ``n_studies``,
  ``buyer_phase``, timestamps. No study UIDs, no presigned URLs.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import distinct, select

from radivault_fulfillment.auth.gateway import require_gateway
from radivault_fulfillment.db.models import Order, OrderItem
from radivault_fulfillment.orders.buyer_phase import buyer_phase_for

log = logging.getLogger("radivault_fulfillment.routers.hospital_orders")

router = APIRouter(tags=["hospital-portal"])


class HospitalOrderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id_masked: str
    n_studies: int
    phase: Literal[
        "accepted",
        "fetching_from_hospital",
        "preparing_download",
        "ready_to_download",
        "completed",
        "cancelled",
        "expired",
        "failed",
    ]
    submitted_at: datetime
    delivered_at: datetime | None = None


class HospitalOrdersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    orders: list[HospitalOrderSummary]
    as_of: datetime


class HospitalOrdersEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: HospitalOrdersResponse


def _mask_order_id(order_id: str) -> str:
    """Return a short opaque prefix (e.g. ``ord_5a3f``) suitable for UI display."""
    if not order_id:
        return "ord_xxxx"
    # Existing order_id pattern is ``ord_<ULID>`` — take the last 4 chars of
    # the ULID suffix for stable-but-opaque short form (no hospital can infer
    # the full ULID from 4 hex).
    suffix = order_id.split("_", 1)[-1][-4:] if "_" in order_id else order_id[-4:]
    return f"ord_{suffix.lower()}"


@router.get(
    "/v1/hospital/me/orders",
    response_model=HospitalOrdersEnvelope,
    summary="Hospital Dashboard — orders that consumed this hospital's studies",
)
def get_hospital_orders(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
) -> HospitalOrdersEnvelope:
    hospital_pk, hospital_id, _gateway_id = require_gateway(request)
    session_factory = request.app.state.session_factory

    now = datetime.now(tz=UTC)
    with session_factory() as session:
        # Join order_item -> order, filter to this hospital, dedupe by
        # order_pk (since a single order can contain multiple items for the
        # same hospital), order by most-recent submitted first.
        order_pk_subq = (
            select(distinct(OrderItem.order_pk))
            .where(OrderItem.hospital_pk == hospital_pk)
            .subquery()
        )
        rows = session.execute(
            select(
                Order.order_id,
                Order.n_studies,
                Order.status,
                Order.submitted_at,
                Order.delivered_at,
            )
            .where(Order.order_pk.in_(select(order_pk_subq)))
            .order_by(Order.submitted_at.desc())
            .limit(limit)
        ).all()

    orders: list[HospitalOrderSummary] = []
    for order_id, n_studies, status, submitted_at, delivered_at in rows:
        if submitted_at is not None and submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=UTC)
        if delivered_at is not None and delivered_at.tzinfo is None:
            delivered_at = delivered_at.replace(tzinfo=UTC)
        orders.append(
            HospitalOrderSummary(
                order_id_masked=_mask_order_id(order_id),
                n_studies=n_studies,
                phase=buyer_phase_for(status),
                submitted_at=submitted_at or now,
                delivered_at=delivered_at,
            )
        )

    return HospitalOrdersEnvelope(
        data=HospitalOrdersResponse(hospital_id=hospital_id, orders=orders, as_of=now)
    )


__all__ = ["router"]
