"""Medical exclusion matcher tests (dev-spec §4.4, FR-25/FR-26)."""

from __future__ import annotations

import pytest

from radivault_gateway.deid.pixel.config import DEFAULT_EXCLUSION_PATTERNS
from radivault_gateway.deid.pixel.exclusion import MedicalExclusionMatcher


@pytest.fixture
def matcher() -> MedicalExclusionMatcher:
    return MedicalExclusionMatcher(DEFAULT_EXCLUSION_PATTERNS)


@pytest.mark.parametrize(
    "description,expected_category",
    [
        ("Dental CBCT maxilla", "dental"),
        ("DENTAL panorex", "dental"),
        ("ENT inspection", "ent"),
        ("facial_trauma complete", "facial_trauma"),
        ("facial-trauma series", "facial_trauma"),
        ("maxillofacial reconstruction", "maxillofacial"),
        ("Sinus CT w/ contrast", "sinus"),
        ("Orbit MR", "orbit"),
        ("Ophthalm eval", "ophthalm"),
    ],
)
def test_positive_matches(
    matcher: MedicalExclusionMatcher,
    description: str,
    expected_category: str,
) -> None:
    """AC-10: default patterns match the exclusion list categories."""
    result = matcher.matches(description)
    assert result.matched is True
    assert result.category == expected_category


def test_brain_mri_does_not_match(matcher: MedicalExclusionMatcher):
    """AC-10 negative: Brain MRI should pass exclusion filter."""
    assert matcher.matches("Brain MRI w/o contrast").matched is False


def test_empty_description_does_not_match(matcher: MedicalExclusionMatcher):
    assert matcher.matches("").matched is False
    assert matcher.matches(None).matched is False


def test_korean_keyword_not_matched_by_default(matcher: MedicalExclusionMatcher):
    """AC-11: Korean-only "치과" is NOT matched by default patterns (flag for v0.2.1)."""
    assert matcher.matches("치과 CBCT").matched is False


def test_custom_pattern_matched():
    custom = MedicalExclusionMatcher(["치과", "부비동"])
    assert custom.matches("치과 파노라마").matched is True
    assert custom.matches("Brain MRI").matched is False


def test_invalid_regex_filtered_at_construction():
    # Empty strings are silently dropped; non-string entries ignored.
    m = MedicalExclusionMatcher(["", "   ", None, "(?i)dental"])  # type: ignore[list-item]
    assert m.matches("DENTAL CBCT").matched is True
