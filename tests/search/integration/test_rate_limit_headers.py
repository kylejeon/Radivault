"""Integration tests for design-spec §2.7 rate-limit / quota response headers.

Every response from a protected endpoint (200 success + 429 errors) must
carry:

    X-RateLimit-Limit
    X-RateLimit-Remaining
    X-RateLimit-Reset
    X-Quota-Limit-Daily
    X-Quota-Remaining-Daily
    X-Quota-Reset-Daily

The success-path response body must also expose Meta.buyer_tier and
Meta.buyer_quota_remaining (design-spec §2.3).
"""

from __future__ import annotations

import pytest

EXPECTED_HEADERS = (
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-Quota-Limit-Daily",
    "X-Quota-Remaining-Daily",
    "X-Quota-Reset-Daily",
)


@pytest.mark.integration
def test_success_response_has_all_headers_and_meta(
    app_client, seeded_buyer, synthetic_studies
) -> None:
    _buyer, bundle = seeded_buyer
    app_client.app.state.redis.flushdb()
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"modality": ["CT"], "limit": 5, "include_facets": False},
    )
    assert resp.status_code == 200, resp.text
    for h in EXPECTED_HEADERS:
        assert h in resp.headers, f"missing header {h}; saw {dict(resp.headers)}"
        # Must be a non-empty integer string.
        assert resp.headers[h].lstrip("-").isdigit(), f"{h}={resp.headers[h]}"

    body = resp.json()
    assert "meta" in body
    assert body["meta"]["buyer_tier"] == "paid"
    # Remaining <= daily budget; must be an int.
    assert isinstance(body["meta"]["buyer_quota_remaining"], int)


@pytest.mark.integration
def test_rate_limited_response_has_headers(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    # Shrink rpm cap.
    for m in app_client.app.user_middleware:
        if getattr(m, "cls", None) and m.cls.__name__ == "RateLimitMiddleware":
            m.kwargs["tier_paid"].rpm = 2
            break
    app_client.app.state.redis.flushdb()

    hdrs = {"Authorization": f"Bearer {bundle.plaintext}"}
    body = {"modality": ["CT"], "limit": 1, "include_facets": False}
    last = None
    for _ in range(5):
        last = app_client.post("/v1/search/studies", headers=hdrs, json=body)
    assert last is not None
    assert last.status_code == 429, last.text
    for h in EXPECTED_HEADERS:
        assert h in last.headers, f"missing header {h} on 429; saw {dict(last.headers)}"
