"""Internal 12-state FSM -> buyer-facing 5-phase mapping (dev-spec buyer-portal-demo §7 D-3).

The internal state machine (:mod:`radivault_fulfillment.orders.state_machine`)
carries 12 operational states. Buyers in the Next.js portal don't need that
density and UX research (`research/buyer-portal-ux-competitive.md §7.2`) shows
a 5-step stepper is what the industry converges on. The server is the source
of truth for the mapping so the portal never drifts.

The three explicit terminals outside the happy-path stepper (``cancelled``,
``expired``, ``failed``) are surfaced as-is — the portal renders them as red
banners not tracker phases.
"""

from __future__ import annotations

from typing import Literal

BuyerPhase = Literal[
    "accepted",
    "fetching_from_hospital",
    "preparing_download",
    "ready_to_download",
    "completed",
    "cancelled",
    "expired",
    "failed",
]

# Mapping is exhaustive against STATES in ``state_machine``. Any future state
# that gets added *must* be appended here or the default case (``accepted``)
# will apply and callers will see a silent fallback. A unit test asserts the
# mapping covers every currently-defined state.
_MAPPING: dict[str, BuyerPhase] = {
    # draft + submitted + validating + validated + queued -> accepted
    "draft": "accepted",
    "submitted": "accepted",
    "validating": "accepted",
    "validated": "accepted",
    "queued": "accepted",
    # actively pulling from gateway
    "fetching": "fetching_from_hospital",
    # staging into central object store
    "staging_partial": "preparing_download",
    "staging_complete": "preparing_download",
    # presigned URLs available
    "ready_for_download": "ready_to_download",
    "delivering": "ready_to_download",
    # happy-path terminal
    "delivered": "completed",
    # sad-path terminals (surface as-is)
    "cancelled": "cancelled",
    "expired": "expired",
    "failed": "failed",
}


def buyer_phase_for(state: str) -> BuyerPhase:
    """Return the buyer-facing phase for the internal ``state``.

    Unknown states fall back to ``accepted`` so the portal's stepper still
    renders a reasonable position instead of crashing. Server-side
    instrumentation owns alerting when this fallback fires.
    """
    return _MAPPING.get(state, "accepted")


def all_mapped_states() -> frozenset[str]:
    """Set of internal states explicitly covered by the mapping."""
    return frozenset(_MAPPING.keys())


__all__ = ["BuyerPhase", "all_mapped_states", "buyer_phase_for"]
