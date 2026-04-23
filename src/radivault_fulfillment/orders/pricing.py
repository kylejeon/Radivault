"""Pricing stub (dev-spec FR-15).

v0.1 MVP: tier.unit_price_usd * n_studies, no real payment gate. The row's
``status_billing`` stays ``pending_billing`` for every order.
"""

from __future__ import annotations

from decimal import Decimal

from radivault_fulfillment.config import TierDefaults


def estimate_order_price(tier: TierDefaults, *, n_studies: int) -> Decimal:
    unit = Decimal(str(tier.unit_price_usd))
    return unit * n_studies


__all__ = ["estimate_order_price"]
