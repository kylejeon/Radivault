"""Unit tests for FR-75/76 — ``scope_json.exclude_hospitals`` application filter.

Covers:
- No scope → all hospitals returned
- Exclude 1 hospital → that hospital's studies + facet counts drop out
- Exclude ALL hospitals → 0 results, no error
- Malformed scope_json.exclude_hospitals → coerced to no-op (defensive)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from radivault_central.db.models import Base as CentralBase
from radivault_central.db.models import Hospital, Study
from radivault_search.db.session import get_engine, reset_for_tests
from radivault_search.query.executor import run_search
from radivault_search.query.schema import SearchRequest
from radivault_search.query.validator import (
    _build_where,
    _extract_exclude_hospitals,
    estimate_cost,
)


@pytest.fixture
def three_hospitals():
    reset_for_tests()
    engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=1, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    hpks: list[int] = []
    with Session(engine) as session:
        for label in ("A", "B", "C"):
            h = Hospital(
                hospital_id=f"h_{label}",
                name=f"Hospital {label}",
                salt_version_current=1,
                allowed_ruleset_versions=[],
            )
            session.add(h)
            session.flush()
            hpks.append(h.hospital_pk)
            for i in range(5):
                session.add(
                    Study(
                        pseudo_study_uid=f"{label}_u_{i:02d}",
                        hospital_pk=h.hospital_pk,
                        modality="CT",
                        study_date_shifted=datetime(2026, 1, 1 + i, tzinfo=UTC).replace(
                            tzinfo=None
                        ),
                        n_instances=1,
                        n_series=1,
                        total_bytes=1,
                        central_job_id=f"j_{label}_{i}",
                        gateway_id="gw",
                    )
                )
        session.commit()
        yield session, hpks
    engine.dispose()
    reset_for_tests()


def test_extract_exclude_hospitals_none() -> None:
    assert _extract_exclude_hospitals(None) == []
    assert _extract_exclude_hospitals({}) == []
    assert _extract_exclude_hospitals({"other": 1}) == []


def test_extract_exclude_hospitals_well_formed() -> None:
    assert _extract_exclude_hospitals({"exclude_hospitals": [1, 2, 3]}) == [1, 2, 3]
    assert _extract_exclude_hospitals({"exclude_hospitals": ("4", "5")}) == [4, 5]


def test_extract_exclude_hospitals_malformed_is_empty() -> None:
    # Non-list values are coerced to empty — never widen access.
    assert _extract_exclude_hospitals({"exclude_hospitals": "not-a-list"}) == []
    assert _extract_exclude_hospitals({"exclude_hospitals": 42}) == []
    # Members that aren't coercible to int are dropped.
    assert _extract_exclude_hospitals({"exclude_hospitals": [1, "foo", None]}) == [1]


def test_run_search_no_scope_returns_all(three_hospitals) -> None:
    session, _hpks = three_hospitals
    req = SearchRequest(limit=100, include_facets=False)
    result = run_search(session, req, buyer_pk=1, global_salt="s")
    assert len(result.response.items) == 15


def test_run_search_excludes_one_hospital(three_hospitals) -> None:
    session, hpks = three_hospitals
    req = SearchRequest(limit=100, include_facets=True)
    result = run_search(
        session,
        req,
        buyer_pk=1,
        global_salt="s",
        scope_json={"exclude_hospitals": [hpks[0]]},
    )
    # 10 studies remain (hospitals B + C)
    assert len(result.response.items) == 10
    # The facet count for modality=CT drops to 10.
    ct = next(
        (f for f in (result.response.facets or {}).get("modality", []) if f.value == "CT"),
        None,
    )
    assert ct is not None
    assert ct.count == 10


def test_run_search_excludes_all_hospitals_returns_zero(three_hospitals) -> None:
    session, hpks = three_hospitals
    req = SearchRequest(limit=100, include_facets=False)
    result = run_search(
        session,
        req,
        buyer_pk=1,
        global_salt="s",
        scope_json={"exclude_hospitals": hpks},
    )
    # No studies match; no error.
    assert result.response.items == []
    assert result.response.page_size == 0
    assert result.total_count == 0


def test_estimate_cost_respects_scope(three_hospitals) -> None:
    session, hpks = three_hospitals
    req = SearchRequest(modality=["CT"], limit=10)
    est_all = estimate_cost(session, req)
    est_scoped = estimate_cost(session, req, scope_json={"exclude_hospitals": [hpks[0]]})
    assert est_all.estimated_rows >= est_scoped.estimated_rows
    assert est_scoped.estimated_rows == 10  # 2 hospitals × 5 studies


def test_build_where_includes_hospital_notin() -> None:
    req = SearchRequest(modality=["CT"])
    clauses = _build_where(req, scope_json={"exclude_hospitals": [7, 8]})
    # Check that the additional clause references hospital_pk.
    rendered = [str(c) for c in clauses]
    assert any("hospital_pk" in r for r in rendered)
