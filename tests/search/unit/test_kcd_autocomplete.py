"""buyer-search-v3 FR-V3-API-4 — KCD autocomplete dictionary search."""

from __future__ import annotations

from radivault_search.query.kcd_dict import ALL_ENTRIES, KCD8, RADLEX, SNOMED, search


def test_dictionary_size() -> None:
    assert len(KCD8) >= 40
    assert len(SNOMED) >= 40
    assert len(RADLEX) >= 40
    assert len(ALL_ENTRIES) == len(KCD8) + len(SNOMED) + len(RADLEX)


def test_search_korean_substring() -> None:
    out = search("협심증", limit=12)
    assert len(out) >= 1
    # KCD-8 I20.9 must be present.
    codes = {r.code for r in out}
    assert "I20.9" in codes


def test_search_english_substring() -> None:
    out = search("Angina", limit=12)
    assert any(r.label_en.lower().startswith("angina") for r in out)


def test_search_code_exact_match_first() -> None:
    out = search("I20.9", limit=3)
    assert out[0].code == "I20.9"


def test_search_caps_per_ontology() -> None:
    out = search("코", limit=12)  # broad Korean substring
    by_ont: dict[str, int] = {}
    for r in out:
        by_ont[r.ontology] = by_ont.get(r.ontology, 0) + 1
    # No single ontology should monopolise the 12-row limit.
    for n in by_ont.values():
        assert n <= 6  # ceil(12/3) + small safety margin


def test_empty_query_returns_empty() -> None:
    assert search("", limit=12) == []
    assert search("   ", limit=12) == []
