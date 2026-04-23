"""Integration tests for FR-19 — tier-specific ``max_limit_per_page`` enforcement.

- preview buyer + limit=200 → 400 ERR_PAGE_LIMIT
- paid buyer + limit=200 → OK
- scope_json.max_limit_per_page override wins over tier default
"""

from __future__ import annotations

import pytest

from radivault_search.auth.buyer_tokens import generate_buyer_key
from radivault_search.db.models import Buyer, BuyerApiKey


def _seed_buyer(factory, *, tier: str, scope_json: dict | None = None):
    bundle = generate_buyer_key()
    with factory() as session:
        buyer = Buyer(
            buyer_id=f"buy_pl_{tier}",
            name=f"{tier} pl",
            contact_email="t@example.com",
            tier=tier,
            active=True,
            scope_json=scope_json or {},
        )
        session.add(buyer)
        session.flush()
        key = BuyerApiKey(
            buyer_pk=buyer.buyer_pk,
            kid=bundle.kid,
            token_hash=bundle.hash,
            tier=tier,
            scope_json=scope_json or {},
        )
        session.add(key)
        session.commit()
    return bundle


@pytest.mark.integration
def test_preview_buyer_over_cap_400(app_client, engine_and_factory, synthetic_studies) -> None:
    _, factory = engine_and_factory
    bundle = _seed_buyer(factory, tier="preview")
    # Reset redis so prior fixtures don't leak rate-limit state.
    app_client.app.state.redis.flushdb()
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"limit": 200, "include_facets": False},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"] == "ERR_PAGE_LIMIT"
    # Detail mentions the cap (100 for preview by default).
    assert "100" in body["detail"] or "limit" in body["detail"].lower()


@pytest.mark.integration
def test_paid_buyer_at_cap_200_ok(app_client, seeded_buyer, synthetic_studies) -> None:
    # The default seeded_buyer is paid tier; cap is 200.
    _buyer, bundle = seeded_buyer
    app_client.app.state.redis.flushdb()
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"limit": 200, "include_facets": False},
    )
    # 200 is == cap; must succeed.
    assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_scope_json_override_raises_cap(app_client, engine_and_factory, synthetic_studies) -> None:
    _, factory = engine_and_factory
    bundle = _seed_buyer(factory, tier="preview", scope_json={"max_limit_per_page": 150})
    app_client.app.state.redis.flushdb()
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"limit": 120, "include_facets": False},
    )
    # override (150) > body.limit (120) — allowed.
    assert resp.status_code == 200, resp.text
