"""Keyset pagination correctness (AC-20, FR-28)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from radivault_central.db.models import Base as CentralBase
from radivault_central.db.models import Hospital, Study
from radivault_search.db.session import get_engine, reset_for_tests
from radivault_search.query.executor import run_search
from radivault_search.query.schema import SearchRequest


@pytest.fixture
def session_with_studies():
    reset_for_tests()
    engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=1, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        h = Hospital(hospital_id="h", name="h", salt_version_current=1, allowed_ruleset_versions=[])
        session.add(h)
        session.flush()
        base = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        for i in range(1000):
            session.add(
                Study(
                    pseudo_study_uid=f"u_{i:04d}",
                    hospital_pk=h.hospital_pk,
                    modality="CT",
                    study_date_shifted=base + timedelta(days=i),
                    n_instances=1,
                    n_series=1,
                    total_bytes=1,
                    central_job_id="j",
                    gateway_id="gw",
                )
            )
        session.commit()
        yield session
    engine.dispose()
    reset_for_tests()


def test_full_walk_no_duplicates(session_with_studies) -> None:
    """AC-20: 1000 studies + limit=50 → 20 pages, no dup/no missing."""
    seen: set[str] = set()
    cursor: str | None = None
    pages = 0
    while True:
        req = SearchRequest(limit=50, cursor=cursor, include_facets=False)
        result = run_search(session_with_studies, req, buyer_pk=1, global_salt="salt")
        pages += 1
        for item in result.response.items:
            assert item.pseudo_study_uid not in seen, "duplicate row"
            seen.add(item.pseudo_study_uid)
        cursor = result.response.next_cursor
        if not result.response.has_next or cursor is None:
            break
        if pages > 25:
            raise AssertionError("too many pages — broken pagination")
    assert len(seen) == 1000
    assert pages == 20
