"""End-to-end search pipeline — router → DB → response shape (AC-1, AC-15, AC-20, AC-23)."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_healthz_public(app_client) -> None:
    resp = app_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.integration
def test_version_public(app_client) -> None:
    resp = app_client.get("/v1/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "0.1.0"
    assert "api_contract_version" in body


@pytest.mark.integration
def test_auth_missing(app_client) -> None:
    resp = app_client.post("/v1/search/studies", json={"limit": 10})
    assert resp.status_code == 401
    env = resp.json()
    assert env["error"] == "ERR_AUTH_MISSING"
    assert "WWW-Authenticate" in resp.headers


@pytest.mark.integration
def test_auth_format(app_client) -> None:
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": "Bearer rv_live_short"},
        json={"limit": 10},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "ERR_AUTH_FORMAT"


@pytest.mark.integration
def test_search_ok_basic(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"modality": ["CT"], "limit": 10, "include_facets": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # items shape (AC-23: no StudyInstanceUID / object_key leakage)
    assert "items" in body
    for item in body["items"]:
        assert "pseudo_study_uid" in item
        assert "StudyInstanceUID" not in item
        assert "object_key" not in item
    assert body["page_size"] == len(body["items"])
    assert "pagination" in body
    assert "meta" in body


@pytest.mark.integration
def test_cursor_filter_changed(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    page1 = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"modality": ["CT"], "limit": 5, "include_facets": False},
    )
    assert page1.status_code == 200
    cursor = page1.json()["next_cursor"]
    assert cursor

    # Changed filter → 400
    page2 = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={
            "modality": ["CT", "MR"],
            "limit": 5,
            "cursor": cursor,
            "include_facets": False,
        },
    )
    assert page2.status_code == 400
    assert page2.json()["error"] == "ERR_CURSOR_FILTER_CHANGED"


@pytest.mark.integration
def test_cursor_version_rejected(app_client, seeded_buyer, synthetic_studies) -> None:
    import base64
    import json

    _buyer, bundle = seeded_buyer
    bogus = {
        "v": 99,
        "d": "2026-01-01",
        "p": 1,
        "s": "x" * 12,
        "k": "date_desc",
    }
    tok = base64.urlsafe_b64encode(json.dumps(bogus).encode()).decode().rstrip("=")
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"modality": ["CT"], "limit": 5, "cursor": tok, "include_facets": False},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "ERR_CURSOR_VERSION"


@pytest.mark.integration
def test_filter_too_many(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    # pydantic's max_length caps at 10 → 400 ERR_REQUEST_SCHEMA via handler.
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"modality": ["CT"] * 11, "limit": 5, "include_facets": False},
    )
    assert resp.status_code == 400


@pytest.mark.integration
def test_facets_suppressed_hint_surfaced(app_client, seeded_buyer, synthetic_studies) -> None:
    """FR-22 / AC-18 — when the estimator flags auto-suppress, the response
    body must contain ``facets: null`` AND a real ``hint`` string."""
    _buyer, bundle = seeded_buyer
    app_state = app_client.app.state
    original = app_state.settings.cost.facet_auto_suppress_rows
    # Drop threshold so the 120-row seed trips suppression.
    app_state.settings.cost.facet_auto_suppress_rows = 10
    try:
        resp = app_client.post(
            "/v1/search/studies",
            headers={"Authorization": f"Bearer {bundle.plaintext}"},
            json={"limit": 10, "include_facets": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["facets"] is None
        assert "hint" in body, body.keys()
        assert body["hint"] == "facets suppressed: cohort too large"
    finally:
        app_state.settings.cost.facet_auto_suppress_rows = original


@pytest.mark.integration
def test_query_too_broad(app_client, seeded_buyer, synthetic_studies) -> None:
    """With the test settings ``max_estimated_rows=1000`` the 120-row dataset
    comfortably fits. We lower the threshold for this test via scope override."""
    _buyer, bundle = seeded_buyer
    # Drop the cap so that our 120-row DB trips the limit.
    app_state = app_client.app.state
    original = app_state.settings.cost.max_estimated_rows
    app_state.settings.cost.max_estimated_rows = 10
    try:
        resp = app_client.post(
            "/v1/search/studies",
            headers={"Authorization": f"Bearer {bundle.plaintext}"},
            json={"limit": 10, "include_facets": False},
        )
        assert resp.status_code == 422
        assert resp.json()["error"] == "ERR_QUERY_TOO_BROAD"
    finally:
        app_state.settings.cost.max_estimated_rows = original


@pytest.mark.integration
def test_study_detail_404(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    resp = app_client.get(
        "/v1/search/studies/does.not.exist",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "ERR_STUDY_NOT_FOUND"


@pytest.mark.integration
def test_hospitals_endpoint(app_client, seeded_buyer, synthetic_studies) -> None:
    _buyer, bundle = seeded_buyer
    resp = app_client.get(
        "/v1/search/hospitals",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hospitals"] >= 1
    for item in body["items"]:
        assert "hospital_opaque_id" in item
        assert item.get("name_public") is None  # default includes no name


@pytest.mark.integration
def test_audit_row_written(app_client, seeded_buyer, synthetic_studies, engine_and_factory) -> None:
    _buyer, bundle = seeded_buyer
    _, factory = engine_and_factory
    resp = app_client.post(
        "/v1/search/studies",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
        json={"modality": ["CT"], "limit": 5, "include_facets": False},
    )
    assert resp.status_code == 200

    # Background task has run by TestClient response time.
    from radivault_search.db.models import SearchAudit

    with factory() as session:
        rows = list(session.query(SearchAudit).all())
        assert len(rows) >= 1
        latest = rows[-1]
        assert latest.endpoint == "/v1/search/studies"
        assert latest.status_code == 200
        assert latest.result_count is not None
        assert len(latest.filter_sha256 or "") == 64
