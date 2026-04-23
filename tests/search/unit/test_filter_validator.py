"""Unit tests for the request validator (FR-17..FR-20)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from radivault_search.errors import FilterTooMany
from radivault_search.query.schema import SearchRequest, StudyDateRange
from radivault_search.query.validator import validate_filter


def test_modality_too_many() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(modality=["CT"] * 11)


def test_modality_at_limit_validator() -> None:
    req = SearchRequest(modality=["CT"] * 10)
    validate_filter(req)  # no raise


def test_validate_filter_raises_at_11() -> None:
    # Build via .model_construct to skip pydantic length cap and hit
    # FilterTooMany path.
    req = SearchRequest.model_construct(modality=["CT"] * 11)
    with pytest.raises(FilterTooMany):
        validate_filter(req)


def test_date_range_bounds_required() -> None:
    with pytest.raises(ValidationError):
        StudyDateRange.model_validate({"from": "2024-01-01"})


def test_date_range_order_check() -> None:
    with pytest.raises(ValidationError):
        StudyDateRange.model_validate({"from": "2026-04-20", "to": "2024-01-01"})


def test_min_hospitals_bounds() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(min_hospitals=0)
    with pytest.raises(ValidationError):
        SearchRequest(min_hospitals=21)


def test_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(limit=0)
    with pytest.raises(ValidationError):
        SearchRequest(limit=201)
