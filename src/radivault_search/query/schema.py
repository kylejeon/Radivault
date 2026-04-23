"""Pydantic request/response models for radivault_search (dev-spec §6.4)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StudyDateRange(BaseModel):
    """Date range with both bounds required (FR-18)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    date_from: date = Field(..., alias="from")
    date_to: date = Field(..., alias="to")

    @model_validator(mode="after")
    def _check_order(self) -> StudyDateRange:
        if self.date_from >= self.date_to:
            raise ValueError("study_date_shifted.from must be < to")
        return self


class SearchRequest(BaseModel):
    """Input body for ``POST /v1/search/studies`` (dev-spec FR-16..FR-20)."""

    model_config = ConfigDict(extra="forbid")

    modality: list[str] | None = Field(None, max_length=10)
    body_part: list[str] | None = Field(None, max_length=10)
    age_bucket: list[str] | None = Field(None, max_length=10)
    sex: list[Literal["M", "F", "O"]] | None = None
    study_date_shifted: StudyDateRange | None = None
    manufacturer: list[str] | None = Field(None, max_length=10)
    min_hospitals: int | None = Field(None, ge=1, le=20)
    sort: Literal["date_desc", "ingested_desc"] = "date_desc"
    limit: int = Field(50, ge=1, le=200)
    cursor: str | None = None
    include_facets: bool = True


class StudyItem(BaseModel):
    pseudo_study_uid: str
    modality: str | None
    body_part: str | None
    age_bucket: str | None
    sex: str | None
    study_date_shifted: date | None
    manufacturer: str | None
    model_name: str | None
    n_instances: int
    n_series: int
    total_bytes: int
    hospital_opaque_id: str
    ingested_at: datetime


class FacetValue(BaseModel):
    value: str | None
    count: int
    is_truncated: bool = False


class Pagination(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False
    page_size: int


class Meta(BaseModel):
    total_hint: int | None = None
    total_count_exact: bool = True
    result_is_approximate: bool = False
    query_duration_ms: int = 0
    buyer_quota_remaining: int | None = None
    buyer_tier: str | None = None
    facets_suppressed: bool = False
    response_truncated: bool = False


class SearchResponse(BaseModel):
    items: list[StudyItem]
    facets: dict[str, list[FacetValue]] | None = None
    pagination: Pagination
    meta: Meta
    total_count: int | None = None
    total_count_exact: bool = True
    next_cursor: str | None = None
    has_next: bool = False
    page_size: int
    response_truncated: bool = False


class SeriesSummary(BaseModel):
    pseudo_series_uid: str
    modality: str | None
    n_instances: int


class SearchStudyDetail(StudyItem):
    series: list[SeriesSummary]


class HospitalItem(BaseModel):
    hospital_opaque_id: str
    study_count: int
    first_study_date: date | None
    last_study_date: date | None
    modalities: list[str]
    name_public: str | None = None


class HospitalsResponse(BaseModel):
    items: list[HospitalItem]
    total_hospitals: int


class FacetsResponse(BaseModel):
    modality: list[FacetValue] = Field(default_factory=list)
    body_part: list[FacetValue] = Field(default_factory=list)
    sex: list[FacetValue] = Field(default_factory=list)
    age_bucket: list[FacetValue] = Field(default_factory=list)
    manufacturer: list[FacetValue] = Field(default_factory=list)
    year: list[FacetValue] = Field(default_factory=list)
    computed_at: datetime


def canonical_filter_dict(req: SearchRequest) -> dict[str, Any]:
    """Return a canonical ``{filter_field: value}`` dict used for sha256 binding.

    The cursor binding sha256 is computed over this dict so adding/removing a
    filter key invalidates the cursor (FR-26).
    """
    out: dict[str, Any] = {}
    if req.modality is not None:
        out["modality"] = sorted(req.modality)
    if req.body_part is not None:
        out["body_part"] = sorted(req.body_part)
    if req.age_bucket is not None:
        out["age_bucket"] = sorted(req.age_bucket)
    if req.sex is not None:
        out["sex"] = sorted(req.sex)
    if req.study_date_shifted is not None:
        out["study_date_shifted"] = {
            "from": req.study_date_shifted.date_from.isoformat(),
            "to": req.study_date_shifted.date_to.isoformat(),
        }
    if req.manufacturer is not None:
        out["manufacturer"] = sorted(req.manufacturer)
    if req.min_hospitals is not None:
        out["min_hospitals"] = req.min_hospitals
    out["sort"] = req.sort
    return out


def filter_fields_list(req: SearchRequest) -> list[str]:
    """Return the list of filter field names present (for JSON log FR-47)."""
    fields: list[str] = []
    for name in (
        "modality",
        "body_part",
        "age_bucket",
        "sex",
        "study_date_shifted",
        "manufacturer",
        "min_hospitals",
    ):
        if getattr(req, name, None) is not None:
            fields.append(name)
    return fields
