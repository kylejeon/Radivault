"""buyer-search-v3 FR-V3-API-4 — GET /v1/search/kcd-autocomplete integration."""

from __future__ import annotations


def _bearer(bundle) -> dict[str, str]:
    return {"Authorization": f"Bearer {bundle.plaintext}"}


def test_kcd_autocomplete_returns_results(app_client, seeded_buyer) -> None:
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/search/kcd-autocomplete?q=협심증&limit=12",
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "computed_at" in body
    items = body["items"]
    assert len(items) >= 1
    codes = {it["code"] for it in items}
    assert "I20.9" in codes


def test_kcd_autocomplete_caps_limit(app_client, seeded_buyer) -> None:
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/search/kcd-autocomplete?q=a&limit=6",
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) <= 6


def test_kcd_autocomplete_requires_auth(app_client) -> None:
    res = app_client.get("/v1/search/kcd-autocomplete?q=test")
    assert res.status_code == 401


def test_kcd_autocomplete_validates_q(app_client, seeded_buyer) -> None:
    _, bundle = seeded_buyer
    # Missing q — radivault_search remaps 422→400 via the global exception
    # handler envelope, so accept either.
    res = app_client.get(
        "/v1/search/kcd-autocomplete", headers=_bearer(bundle)
    )
    assert res.status_code in (400, 422)
    # Too long q.
    res = app_client.get(
        f"/v1/search/kcd-autocomplete?q={'x' * 200}",
        headers=_bearer(bundle),
    )
    assert res.status_code in (400, 422)
