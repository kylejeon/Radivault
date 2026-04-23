"""Unit tests for 12-state -> 5-phase buyer-facing mapping (D-3).

AC-D-3: every internal state in :data:`state_machine.STATES` resolves to a
specific ``buyer_phase`` label; the three terminal error states surface as-is;
the portal's 5-phase stepper never receives an unmapped state.
"""

from __future__ import annotations

import pytest

from radivault_fulfillment.orders.buyer_phase import (
    all_mapped_states,
    buyer_phase_for,
)
from radivault_fulfillment.orders.state_machine import STATES


def test_every_known_state_has_a_mapping():
    unmapped = STATES - all_mapped_states()
    assert unmapped == set(), f"unmapped internal states: {sorted(unmapped)}"


@pytest.mark.parametrize(
    "state,phase",
    [
        ("draft", "accepted"),
        ("submitted", "accepted"),
        ("validating", "accepted"),
        ("validated", "accepted"),
        ("queued", "accepted"),
        ("fetching", "fetching_from_hospital"),
        ("staging_partial", "preparing_download"),
        ("staging_complete", "preparing_download"),
        ("ready_for_download", "ready_to_download"),
        ("delivering", "ready_to_download"),
        ("delivered", "completed"),
        ("cancelled", "cancelled"),
        ("expired", "expired"),
        ("failed", "failed"),
    ],
)
def test_mapping_matches_dev_spec_table(state, phase):
    assert buyer_phase_for(state) == phase


def test_unknown_state_falls_back_to_accepted():
    assert buyer_phase_for("some_state_from_the_future") == "accepted"


def test_mapping_is_stable_across_calls():
    first = {s: buyer_phase_for(s) for s in STATES}
    second = {s: buyer_phase_for(s) for s in STATES}
    assert first == second
