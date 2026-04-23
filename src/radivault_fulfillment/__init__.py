"""RadiVault Order Fulfillment — buyer orders + transfer-job orchestration (Zone 2).

Implements ``docs/specs/dev-spec-order-fulfillment.md`` (85 FRs, 40 AC). The
service exposes two planes:

- Buyer-facing REST ``/v1/orders/*`` — authenticated by metadata-index's
  ``buyer_api_key`` table (read-only reuse).
- Gateway-facing REST ``/v1/gateway/transfer-jobs/*`` — authenticated by
  central-ingest's ``auth_token`` table (read-only reuse).

Port: 8002 (central=8000, search=8001).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
