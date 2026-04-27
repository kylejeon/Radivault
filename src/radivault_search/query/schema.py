"""Pydantic request/response models for radivault_search (dev-spec §6.4).

v3 (dev-spec-buyer-search-v3 FR-V3-API-1/2/3) extensions:
- ``SearchRequest``: ``age_min``, ``age_max``, ``kcd_code``, ``model_name``,
  ``hospital_region`` filters; 9 new sort enums.
- ``StudyItem``: ``hospital_region_pseudo``, ``kcd_code``, ``kcd_label_ko``,
  ``kcd_label_en``, ``patient_age``.
- ``FacetsResponse``: ``hospital_region``, ``kcd_code`` new facets.
  ``age_bucket`` retained but always empty (dev-spec §4.2 deprecation).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# v3 sort enum — 2 legacy + 18 new (9 columns × asc/desc).
SortKey = Literal[
    "date_desc",
    "ingested_desc",
    # v3 — sortable columns from design-spec §8.
    "hospital_asc",
    "hospital_desc",
    "date_asc",
    "modality_asc",
    "modality_desc",
    "body_part_asc",
    "body_part_desc",
    "kcd_asc",
    "kcd_desc",
    "age_asc",
    "age_desc",
    "manufacturer_asc",
    "manufacturer_desc",
    "model_asc",
    "model_desc",
    "size_asc",
    "size_desc",
]


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
    age_bucket: list[str] | None = Field(
        None,
        max_length=10,
        description="DEPRECATED — use age_min/age_max. Ignored when both are set.",
    )
    # v3 FR-V3-API-1 — exact age filter.
    age_min: int | None = Field(None, ge=0, le=120)
    age_max: int | None = Field(None, ge=0, le=120)
    # v3 — KCD-8 code filter (e.g. ["I20.9", "I25.1"]).
    kcd_code: list[str] | None = Field(None, max_length=20)
    # v3 — model_name as a filter (facet existed already).
    model_name: list[str] | None = Field(None, max_length=20)
    # v3 — hospital region pseudo filter (e.g. ["SEOUL-A"]).
    hospital_region: list[str] | None = Field(None, max_length=20)
    sex: list[Literal["M", "F", "O"]] | None = None
    study_date_shifted: StudyDateRange | None = None
    manufacturer: list[str] | None = Field(None, max_length=10)
    min_hospitals: int | None = Field(None, ge=1, le=20)
    sort: SortKey = "date_desc"
    limit: int = Field(50, ge=1, le=200)
    cursor: str | None = None
    include_facets: bool = True
    # text-search-description FR-TS-2 — free-text search query, parsed by
    # ``websearch_to_tsquery('english', :q)`` against the GENERATED tsvector.
    # ``None`` and empty/whitespace-only strings both fall through to the
    # facet-only path so legacy clients are 100% backwards compatible.
    q: str | None = Field(
        None,
        max_length=200,
        description=(
            "Free-text search query; parsed via Postgres "
            "websearch_to_tsquery against study.search_text."
        ),
    )

    @model_validator(mode="after")
    def _check_age_range(self) -> SearchRequest:
        if (
            self.age_min is not None
            and self.age_max is not None
            and self.age_min > self.age_max
        ):
            raise ValueError("age_min must be <= age_max")
        return self

    @model_validator(mode="after")
    def _coerce_blank_q_to_none(self) -> SearchRequest:
        # FR-TS-2 — treat ``""`` / whitespace-only as ``None`` so the executor
        # never branches on a blank string.
        if self.q is not None and not self.q.strip():
            object.__setattr__(self, "q", None)
        return self


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
    # dev-spec-buyer-browse-preview FR-PREVIEW-1: preview gate exposure on
    # search results so the StudyCard can render the JPEG slot vs the
    # placeholder without an extra round-trip. Both fields are optional —
    # older response shapes still validate.
    preview_status: str | None = None
    preview_slice_count: int | None = None
    # v3 (FR-V3-API-2) — exact patient_age + hospital region pseudo + KCD.
    patient_age: int | None = None
    hospital_region_pseudo: str | None = None
    kcd_code: str | None = None
    kcd_label_ko: str | None = None
    kcd_label_en: str | None = None
    # text-search-description FR-TS-9 — server-rendered ts_headline snippet
    # (e.g. ``BRAIN <mark>MR</mark>``) when ``q`` is supplied. Always ``None``
    # in the facet-only response shape, so the regression contract holds.
    highlight_snippet: str | None = None


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
    # text-search-description FR-TS-2 / AC-TS-API-1. ``True`` only when ``q``
    # was non-empty and actually wired into the WHERE/ORDER BY of this query.
    text_search_applied: bool = False
    # FR-TS-10 — pattern names that fired during PHI scrub of ``q``. Empty
    # list when ``q`` is None or contained no PHI; allows the portal UI to
    # mount ``<MaskedQueryBadge>`` without a second round-trip.
    phi_flagged_patterns: list[str] = Field(default_factory=list)


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
    # FR-22 — populated when facet_auto_suppress fires (cohort too large).
    hint: str | None = None


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
    # metadata-thumbnail-ingest FR-FACET-1 — 8 facets total. ``model_name`` is
    # study.manufacturer_model_name; ``contrast_used`` is a v0.1.5 stub.
    model_name: list[FacetValue] = Field(default_factory=list)
    year: list[FacetValue] = Field(default_factory=list)
    contrast_used: list[FacetValue] = Field(default_factory=list)
    # v3 FR-V3-API-3 — new facets.
    hospital_region: list[FacetValue] = Field(default_factory=list)
    kcd_code: list[FacetValue] = Field(default_factory=list)
    computed_at: datetime


class KCDAutocompleteItem(BaseModel):
    """One row of GET /v1/search/kcd-autocomplete (FR-V3-API-4)."""

    ontology: Literal["KCD-8", "SNOMED", "RadLex"]
    code: str
    label_ko: str
    label_en: str


class KCDAutocompleteResponse(BaseModel):
    items: list[KCDAutocompleteItem]
    computed_at: datetime


class AutocompleteSuggestion(BaseModel):
    """One suggestion row returned by GET /v1/search/autocomplete (FR-TS-8).

    ``field`` lets the dropdown render a small badge ("body_part", "modality",
    etc.). ``score`` is the pg_trgm ``word_similarity`` value, kept for
    debugging — clients render but should not depend on a particular range.
    """

    text: str
    field: str
    score: float


class AutocompleteResponse(BaseModel):
    suggestions: list[AutocompleteSuggestion]
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
    # v3 — ignore age_bucket when age_min/max present (FR-V3-API-1 deprecation).
    if req.age_bucket is not None and req.age_min is None and req.age_max is None:
        out["age_bucket"] = sorted(req.age_bucket)
    if req.age_min is not None:
        out["age_min"] = req.age_min
    if req.age_max is not None:
        out["age_max"] = req.age_max
    if req.kcd_code is not None:
        out["kcd_code"] = sorted(req.kcd_code)
    if req.model_name is not None:
        out["model_name"] = sorted(req.model_name)
    if req.hospital_region is not None:
        out["hospital_region"] = sorted(req.hospital_region)
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
    # text-search-description FR-TS-2 — bind q into the cursor sha so a buyer
    # cannot reuse a page-1 cursor against a different ``q`` on page 2.
    if getattr(req, "q", None) is not None:
        out["q"] = req.q
    out["sort"] = req.sort
    return out


def filter_fields_list(req: SearchRequest) -> list[str]:
    """Return the list of filter field names present (for JSON log FR-47).

    text-search-description FR-TS-2 / NFR-TS-AUDIT-2: ``q`` is treated as a
    filter field for the purposes of audit grouping when it is non-empty.
    """
    fields: list[str] = []
    for name in (
        "modality",
        "body_part",
        "age_bucket",
        "age_min",
        "age_max",
        "kcd_code",
        "model_name",
        "hospital_region",
        "sex",
        "study_date_shifted",
        "manufacturer",
        "min_hospitals",
        "q",
    ):
        if getattr(req, name, None) is not None:
            fields.append(name)
    return fields
