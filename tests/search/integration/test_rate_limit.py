"""Per-buyer rate-limit and quota integration tests (AC-8, AC-9)."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_rpm_limit(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    # Force preview tier rpm cap to 3 for the test.
    for m in app_client.app.user_middleware:
        cls = getattr(m, "cls", None)
        if cls and cls.__name__ == "RateLimitMiddleware":
            m.kwargs["tier_paid"].rpm = 3
            break

    # Our seeded buyer is paid tier — patch to reuse the paid limits.
    hdrs = {"Authorization": f"Bearer {bundle.plaintext}"}
    body = {"modality": ["CT"], "limit": 5, "include_facets": False}
    statuses = []
    for _ in range(5):
        r = app_client.post("/v1/search/studies", headers=hdrs, json=body)
        statuses.append(r.status_code)
    # Some requests should have returned 429 once the rpm cap (3) is hit.
    assert 429 in statuses, f"expected 429 in {statuses}"
    # One more call — verify the 429 envelope shape.
    r = app_client.post("/v1/search/studies", headers=hdrs, json=body)
    assert r.status_code == 429
    body429 = r.json()
    assert body429["error"] in {"ERR_RATE_LIMITED", "ERR_BUYER_QUOTA", "ERR_BUYER_CONCURRENCY"}


@pytest.mark.integration
def test_quota_exhausted(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    # Shrink daily limit to 2 via middleware kwargs.
    for m in app_client.app.user_middleware:
        cls = getattr(m, "cls", None)
        if cls and cls.__name__ == "RateLimitMiddleware":
            m.kwargs["tier_paid"].daily = 2
            m.kwargs["tier_paid"].rpm = 100  # avoid rpm trip first
            break

    # Reset the fakeredis so previous test state doesn't leak.
    app_client.app.state.redis.flushdb()

    hdrs = {"Authorization": f"Bearer {bundle.plaintext}"}
    body = {"modality": ["CT"], "limit": 1, "include_facets": False}
    first = app_client.post("/v1/search/studies", headers=hdrs, json=body)
    second = app_client.post("/v1/search/studies", headers=hdrs, json=body)
    third = app_client.post("/v1/search/studies", headers=hdrs, json=body)
    assert first.status_code in {200, 429}
    assert third.status_code == 429
    assert third.json()["error"] in {"ERR_BUYER_QUOTA", "ERR_RATE_LIMITED"}
    _ = second
