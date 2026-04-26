"""buyer-search-v3 FR-V3-DATA-1/2 — exact PatientAge + KCD on extract."""

from __future__ import annotations

from radivault_gateway.extract import (
    _parse_age_exact,
    _parse_birthdate_age_exact,
)


def test_parse_age_exact_years() -> None:
    assert _parse_age_exact("030Y") == 30
    assert _parse_age_exact("089Y") == 89
    assert _parse_age_exact("000Y") == 0
    assert _parse_age_exact("120Y") == 120


def test_parse_age_exact_months() -> None:
    # 36 months → 3 years.
    assert _parse_age_exact("036M") == 3


def test_parse_age_exact_rejects_invalid() -> None:
    assert _parse_age_exact(None) is None
    assert _parse_age_exact("") is None
    assert _parse_age_exact("???") is None
    assert _parse_age_exact("121Y") is None  # over cap.
    assert _parse_age_exact("030D") is None  # days out of scope.
    assert _parse_age_exact("030W") is None


def test_parse_birthdate_age_exact() -> None:
    # 1980-05-15 → 2024-08-15: birthday already passed → 44.
    assert _parse_birthdate_age_exact("19800515", "20240815") == 44
    # Birthday not yet passed.
    assert _parse_birthdate_age_exact("19800515", "20240314") == 43
    # Negative → None.
    assert _parse_birthdate_age_exact("20300101", "20240101") is None
