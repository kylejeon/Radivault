"""Error taxonomy — envelope shape + doc_url rewrite."""

from __future__ import annotations

from radivault_search.errors import (
    BuyerQuota,
    CursorFilterChanged,
    FilterTooMany,
    QueryTimeout,
    QueryTooBroad,
    RequestSchema,
    StudyNotFound,
)


def test_all_new_codes_have_docs() -> None:
    codes = [
        (FilterTooMany(), 400, "ERR_FILTER_TOO_MANY"),
        (CursorFilterChanged(), 400, "ERR_CURSOR_FILTER_CHANGED"),
        (QueryTooBroad(), 422, "ERR_QUERY_TOO_BROAD"),
        (QueryTimeout(), 504, "ERR_QUERY_TIMEOUT"),
        (BuyerQuota(), 429, "ERR_BUYER_QUOTA"),
        (StudyNotFound(), 404, "ERR_STUDY_NOT_FOUND"),
        (RequestSchema(), 400, "ERR_REQUEST_SCHEMA"),
    ]
    for exc, status, code in codes:
        env = exc.to_envelope("rid-123")
        assert env["error"] == code
        assert env["request_id"] == "rid-123"
        assert env["doc_url"].startswith("https://docs.radivault.io/search/errors/")
        assert exc.status_code == status


def test_envelope_has_required_fields() -> None:
    env = QueryTooBroad(detail="too many").to_envelope("r1")
    for key in ("error", "detail", "message_ko", "message_en", "request_id", "doc_url"):
        assert key in env
