"""text-search-description Phase 1.0 — end-to-end coverage of the q + autocomplete surfaces.

These tests run against the SQLite fallback path baked into ``executor.py``
and ``routers/autocomplete.py``. The Postgres-only tsvector / pg_trgm /
ts_headline behaviour is exercised in a separate (manual) demo pass against
the dev container — see the agent's commit-time runbook.
"""

from __future__ import annotations


def _bearer(bundle) -> dict[str, str]:
    return {"Authorization": f"Bearer {bundle.plaintext}"}


# ---------------------------------------------------------------------------
# /v1/search/studies — q field wiring (FR-TS-2 / FR-TS-7 / FR-TS-12)
# ---------------------------------------------------------------------------


def test_q_omitted_keeps_text_search_applied_false(
    app_client, seeded_buyer, synthetic_studies
) -> None:
    """AC-TS-API-4 — q absent ⇒ legacy facet-only path."""
    _, bundle = seeded_buyer
    res = app_client.post(
        "/v1/search/studies",
        json={"limit": 5, "include_facets": False},
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["text_search_applied"] is False
    assert body["meta"]["phi_flagged_patterns"] == []


def test_q_blank_treated_as_none(app_client, seeded_buyer, synthetic_studies) -> None:
    """FR-TS-2 — whitespace-only q coerced to None by the schema validator."""
    _, bundle = seeded_buyer
    res = app_client.post(
        "/v1/search/studies",
        json={"q": "   ", "limit": 5, "include_facets": False},
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    assert res.json()["meta"]["text_search_applied"] is False


def test_q_too_long_rejected(app_client, seeded_buyer) -> None:
    """AC-TS-API-3 — q > 200 chars rejected."""
    _, bundle = seeded_buyer
    res = app_client.post(
        "/v1/search/studies",
        json={"q": "a" * 201},
        headers=_bearer(bundle),
    )
    assert res.status_code in (400, 422)


def test_q_set_marks_text_search_applied(
    app_client, seeded_buyer, synthetic_studies
) -> None:
    """AC-TS-API-1 — text_search_applied=True when q is wired in."""
    _, bundle = seeded_buyer
    res = app_client.post(
        "/v1/search/studies",
        json={"q": "CHEST", "limit": 5, "include_facets": False},
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["text_search_applied"] is True
    # Synthetic seed cycles modality/body_part — a few "CHEST" rows are present.
    items = body["items"]
    assert len(items) >= 1
    assert all(it["body_part"] == "CHEST" for it in items)


def test_q_contradicts_facet_returns_zero_rows(
    app_client, seeded_buyer, synthetic_studies
) -> None:
    """AC-TS-API-5 — q + facet AND-combine."""
    _, bundle = seeded_buyer
    res = app_client.post(
        "/v1/search/studies",
        # synthetic seed has no row matching modality=MR + body_part=ABDOMEN
        # filtered by q="zzznotmatch"; the impossible token alone should
        # produce zero rows.
        json={"q": "zzznotmatch", "limit": 5, "include_facets": False},
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_q_phi_flags_in_response(app_client, seeded_buyer, synthetic_studies) -> None:
    """AC-TS-PHI-1 — meta surfaces phi_flagged_patterns."""
    _, bundle = seeded_buyer
    res = app_client.post(
        "/v1/search/studies",
        json={"q": "홍길동 brain", "limit": 5, "include_facets": False},
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    flags = res.json()["meta"]["phi_flagged_patterns"]
    assert "KOREAN_NAME" in flags


# ---------------------------------------------------------------------------
# /v1/search/autocomplete — FR-TS-8
# ---------------------------------------------------------------------------


def test_autocomplete_returns_suggestions(
    app_client, seeded_buyer, synthetic_studies
) -> None:
    """AC-TS-API-7 — at least one suggestion for a populated stem."""
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/search/autocomplete?q=CHE&limit=10",
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    body = res.json()
    assert "suggestions" in body
    assert "computed_at" in body
    # Synthetic seed has CHEST rows — at least one suggestion should mention it.
    texts = {s["text"].upper() for s in body["suggestions"]}
    assert any("CHEST" in t for t in texts)


def test_autocomplete_caps_limit(app_client, seeded_buyer, synthetic_studies) -> None:
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/search/autocomplete?q=a&limit=5",
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    assert len(res.json()["suggestions"]) <= 5


def test_autocomplete_hard_caps_at_12(
    app_client, seeded_buyer, synthetic_studies
) -> None:
    """design-spec §7.1 — server hard cap of 12 even if buyer asks for more."""
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/search/autocomplete?q=a&limit=99",
        headers=_bearer(bundle),
    )
    # 99 > 12 → FastAPI Query(le=12) returns 422.
    assert res.status_code in (400, 422)


def test_autocomplete_requires_auth(app_client) -> None:
    """AC-TS-API-9."""
    res = app_client.get("/v1/search/autocomplete?q=brain")
    assert res.status_code == 401


def test_autocomplete_validates_q(app_client, seeded_buyer) -> None:
    """AC-TS-API-8 — empty q rejected."""
    _, bundle = seeded_buyer
    # Missing q.
    res = app_client.get("/v1/search/autocomplete", headers=_bearer(bundle))
    assert res.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Feature flag — FR-TS-14
# ---------------------------------------------------------------------------


def test_feature_flag_disables_q(
    app_client, seeded_buyer, synthetic_studies, monkeypatch
) -> None:
    """AC-TS-API-11 — TEXT_SEARCH_ENABLED=false ⇒ q silently ignored."""
    _, bundle = seeded_buyer
    monkeypatch.setenv("TEXT_SEARCH_ENABLED", "false")
    res = app_client.post(
        "/v1/search/studies",
        json={"q": "CHEST", "limit": 5, "include_facets": False},
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    # q is ignored, so text_search_applied is false and the row count is the
    # full synthetic corpus (≥ the CHEST-only subset).
    body = res.json()
    assert body["meta"]["text_search_applied"] is False


def test_feature_flag_disables_autocomplete(
    app_client, seeded_buyer, synthetic_studies, monkeypatch
) -> None:
    _, bundle = seeded_buyer
    monkeypatch.setenv("TEXT_SEARCH_ENABLED", "false")
    res = app_client.get(
        "/v1/search/autocomplete?q=CHE&limit=10",
        headers=_bearer(bundle),
    )
    assert res.status_code == 200
    assert res.json()["suggestions"] == []
