"""Unit tests for :func:`resolve_flow_a_method_codes`.

Flow A method codes are a static ruleset-scoped declaration (the pipeline
never inspects per-instance tags), so the resolver is a thin dict lookup —
but the contract matters: unregistered rulesets must raise, not silently
return ``[]`` (Central's ManifestValidator would otherwise accept an
empty method_code_sequence and break the audit trail).
"""

from __future__ import annotations

import pytest

from radivault_gateway.deid.method_codes import (
    FLOW_A_METHOD_CODES_BY_RULESET,
    resolve_flow_a_method_codes,
)


def test_resolve_flow_a_method_codes_v0_1_0_returns_basic_annex_e_code():
    codes = resolve_flow_a_method_codes("v0.1.0")
    assert codes == ["113100"]


def test_resolve_flow_a_method_codes_returns_fresh_list_each_call():
    """The resolver must return a copy — a caller mutation must not leak
    into the module-level table and contaminate other studies."""
    first = resolve_flow_a_method_codes("v0.1.0")
    first.append("999999")
    second = resolve_flow_a_method_codes("v0.1.0")
    assert second == ["113100"]
    assert FLOW_A_METHOD_CODES_BY_RULESET["v0.1.0"] == ["113100"]


def test_resolve_flow_a_method_codes_unknown_ruleset_raises_value_error():
    with pytest.raises(ValueError) as exc:
        resolve_flow_a_method_codes("v9.9.9")
    # Error message must carry the offending version for triage.
    assert "v9.9.9" in str(exc.value)


def test_resolve_flow_a_method_codes_empty_string_raises():
    with pytest.raises(ValueError):
        resolve_flow_a_method_codes("")
