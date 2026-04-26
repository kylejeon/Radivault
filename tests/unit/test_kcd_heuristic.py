"""buyer-search-v3 FR-V3-DATA-2 — kcd_heuristic table coverage."""

from __future__ import annotations

from radivault_gateway.kcd_heuristic import DEFAULT_ENTRY, all_rules, lookup_kcd


def test_lookup_returns_default_when_missing() -> None:
    assert lookup_kcd("UNKNOWN_MOD", "CHEST") is DEFAULT_ENTRY
    assert lookup_kcd("CT", "UNKNOWN_PART") is DEFAULT_ENTRY
    assert lookup_kcd(None, "CHEST") is DEFAULT_ENTRY
    assert lookup_kcd("CT", None) is DEFAULT_ENTRY


def test_lookup_known_combinations() -> None:
    e = lookup_kcd("CT", "CHEST")
    assert e.code == "I20.9"
    assert "협심증" in e.label_ko
    assert "Angina" in e.label_en

    e = lookup_kcd("MG", "BREAST")
    assert e.code == "C50.9"


def test_lookup_case_insensitive() -> None:
    a = lookup_kcd("ct", "chest")
    b = lookup_kcd("CT", "CHEST")
    assert a.code == b.code == "I20.9"


def test_table_has_at_least_16_rules() -> None:
    rules = all_rules()
    assert len(rules) >= 16
    # Default fallback is intentionally NOT in the rules dict.
    assert ("UNKNOWN", "UNKNOWN") not in rules
