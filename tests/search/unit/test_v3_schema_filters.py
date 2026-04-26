"""buyer-search-v3 FR-V3-API-1/2 — schema filter validation + sort enums."""

from __future__ import annotations

import pytest

from radivault_search.query.schema import (
    SearchRequest,
    canonical_filter_dict,
    filter_fields_list,
)


def test_age_min_le_max_required() -> None:
    with pytest.raises(ValueError):
        SearchRequest(age_min=60, age_max=40)


def test_age_min_max_pass_through() -> None:
    req = SearchRequest(age_min=35, age_max=50)
    d = canonical_filter_dict(req)
    assert d["age_min"] == 35
    assert d["age_max"] == 50
    fields = filter_fields_list(req)
    assert "age_min" in fields
    assert "age_max" in fields


def test_kcd_and_hospital_region_filters() -> None:
    req = SearchRequest(
        kcd_code=["I20.9", "I63.9"],
        hospital_region=["SEOUL-A"],
        model_name=["SOMATOM Drive"],
    )
    d = canonical_filter_dict(req)
    assert d["kcd_code"] == ["I20.9", "I63.9"]
    assert d["hospital_region"] == ["SEOUL-A"]
    assert d["model_name"] == ["SOMATOM Drive"]


def test_age_bucket_ignored_when_age_min_present() -> None:
    req = SearchRequest(age_bucket=["50-54"], age_min=40, age_max=60)
    d = canonical_filter_dict(req)
    assert "age_bucket" not in d
    assert d["age_min"] == 40
    assert d["age_max"] == 60


def test_v3_sort_enum_accepted() -> None:
    for s in (
        "hospital_asc",
        "hospital_desc",
        "modality_asc",
        "kcd_desc",
        "age_asc",
        "size_desc",
    ):
        req = SearchRequest(sort=s)
        assert req.sort == s


def test_legacy_sort_still_works() -> None:
    assert SearchRequest(sort="date_desc").sort == "date_desc"
    assert SearchRequest(sort="ingested_desc").sort == "ingested_desc"
