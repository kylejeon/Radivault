"""text-search-description FR-TS-10 — PHI scrub for search-bar input.

Each canonical pattern from §6.4 has a positive and a negative test. Order-
sensitive cases (RRN before LONG_DIGIT) live in the bottom block.
"""

from __future__ import annotations

import pytest

from radivault_search.audit.phi_scrub import (
    PATTERNS,
    ScrubResult,
    mask_query,
    scrub_query,
)


# ---------------------------------------------------------------------------
# Empty / null guards
# ---------------------------------------------------------------------------


def test_none_returns_empty() -> None:
    res = scrub_query(None)
    assert res == ScrubResult(masked="", patterns=[])


def test_empty_string_returns_empty() -> None:
    res = scrub_query("")
    assert res == ScrubResult(masked="", patterns=[])


# ---------------------------------------------------------------------------
# 7 PHI patterns — positive matches (AC-TS-PHI-1..6)
# ---------------------------------------------------------------------------


def test_korean_name_match() -> None:
    res = scrub_query("홍길동 brain")
    assert "[REDACTED:KOREAN_NAME]" in res.masked
    assert "KOREAN_NAME" in res.patterns
    # The medical token survives.
    assert "brain" in res.masked


def test_english_name_match() -> None:
    res = scrub_query("Smith Brain MRI")
    # ``Smith Brain`` matches the cap-cap pattern; ``MRI`` is uppercase but
    # not titlecase so it does not.
    assert "ENGLISH_NAME" in res.patterns
    assert "[REDACTED:ENGLISH_NAME]" in res.masked


def test_rrn_match() -> None:
    res = scrub_query("900101-1234567 chest")
    assert res.masked == "[REDACTED:RRN] chest"
    assert res.patterns == ["RRN"]


def test_rrn_match_no_hyphen() -> None:
    res = scrub_query("9001011234567 chest")
    assert "[REDACTED:RRN]" in res.masked
    # LONG_DIGIT must NOT also fire — RRN ate the span first.
    assert "LONG_DIGIT" not in res.patterns


def test_mrn_match() -> None:
    res = scrub_query("MRN 12345 brain")
    assert "[REDACTED:MRN]" in res.masked
    assert "MRN" in res.patterns


def test_mrn_with_colon() -> None:
    res = scrub_query("ID:98765 chest CT")
    assert "[REDACTED:MRN]" in res.masked
    assert "MRN" in res.patterns


def test_phone_match() -> None:
    res = scrub_query("010-1234-5678 brain")
    assert "[REDACTED:PHONE]" in res.masked
    assert res.patterns == ["PHONE"]


def test_email_match() -> None:
    res = scrub_query("kyle@radivault.io brain")
    assert "[REDACTED:EMAIL]" in res.masked
    assert "EMAIL" in res.patterns


def test_long_digit_match() -> None:
    # 7+ digits without an MRN prefix or RRN shape.
    res = scrub_query("1234567 brain")
    assert "[REDACTED:LONG_DIGIT]" in res.masked
    assert res.patterns == ["LONG_DIGIT"]


# ---------------------------------------------------------------------------
# Negative cases (AC-TS-PHI-6)
# ---------------------------------------------------------------------------


def test_clean_query_passes_through() -> None:
    res = scrub_query("MR brain")
    assert res.masked == "MR brain"
    assert res.patterns == []
    assert res.redaction_count == 0


def test_short_digit_not_flagged() -> None:
    # 6-digit standalone numbers should not match LONG_DIGIT (≥7 required).
    res = scrub_query("series 123456")
    assert "REDACTED" not in res.masked


def test_lowercase_word_not_english_name() -> None:
    res = scrub_query("brain mri")
    assert res.patterns == []


# ---------------------------------------------------------------------------
# Order-of-precedence (RRN beats LONG_DIGIT, MRN beats LONG_DIGIT)
# ---------------------------------------------------------------------------


def test_rrn_consumed_before_long_digit() -> None:
    res = scrub_query("900101-1234567")
    assert res.patterns == ["RRN"]


def test_mrn_consumed_before_long_digit() -> None:
    res = scrub_query("MRN 9876543")
    # MRN regex eats the entire span ``MRN 9876543`` so LONG_DIGIT cannot
    # also match the trailing 7 digits.
    assert res.patterns == ["MRN"]


# ---------------------------------------------------------------------------
# Multiple patterns in one query
# ---------------------------------------------------------------------------


def test_multiple_patterns_in_one_query() -> None:
    res = scrub_query("홍길동 010-1234-5678 brain MRN 999999")
    # KOREAN_NAME, MRN, PHONE all expected.
    assert "KOREAN_NAME" in res.patterns
    assert "PHONE" in res.patterns
    assert "MRN" in res.patterns
    # Pattern names are unique even if a regex matches twice.
    assert len(res.patterns) == len(set(res.patterns))


# ---------------------------------------------------------------------------
# Back-compat shim
# ---------------------------------------------------------------------------


def test_mask_query_shim_returns_tuple() -> None:
    masked, count = mask_query("홍길동 brain")
    assert "REDACTED" in masked
    assert count >= 1


def test_pattern_table_well_formed() -> None:
    # 7 patterns per dev-spec FR-TS-10.
    assert len(PATTERNS) == 7
    names = [name for name, _ in PATTERNS]
    assert set(names) == {
        "RRN",
        "MRN",
        "PHONE",
        "EMAIL",
        "ENGLISH_NAME",
        "KOREAN_NAME",
        "LONG_DIGIT",
    }


# ---------------------------------------------------------------------------
# Performance smoke — single scrub must stay well under 5 ms (NFR-TS-PERF-4).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "MR brain",
        "홍길동 brain MRN 12345",
        "Smith, J. Brain MR 010-1234-5678 kyle@radivault.io",
    ],
)
def test_scrub_under_5ms_smoke(raw: str) -> None:
    import time

    # Average over a small batch to dampen scheduler noise.
    start = time.perf_counter()
    for _ in range(200):
        scrub_query(raw)
    elapsed_ms = (time.perf_counter() - start) * 1000 / 200
    # Generous — 5 ms is the production p95 budget; even on tiny CI runners
    # a single regex pass should be sub-millisecond.
    assert elapsed_ms < 5.0, f"scrub avg {elapsed_ms:.2f} ms > 5 ms"
