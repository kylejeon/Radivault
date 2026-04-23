"""Cost estimator unit tests (FR-21)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from radivault_central.db.models import Base as CentralBase
from radivault_central.db.models import Hospital, Study
from radivault_search.db.session import get_engine, reset_for_tests
from radivault_search.query.schema import SearchRequest, StudyDateRange
from radivault_search.query.validator import estimate_cost


@pytest.fixture
def engine():
    reset_for_tests()
    e = get_engine("sqlite+pysqlite:///:memory:", pool_size=1, max_overflow=0)
    CentralBase.metadata.create_all(e)
    yield e
    e.dispose()
    reset_for_tests()


def test_estimator_returns_count_on_sqlite(engine) -> None:
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        hospital = Hospital(
            hospital_id="h1", name="h", salt_version_current=1, allowed_ruleset_versions=["v0.1.0"]
        )
        session.add(hospital)
        session.flush()
        for i in range(5):
            session.add(
                Study(
                    pseudo_study_uid=f"uid_{i}",
                    hospital_pk=hospital.hospital_pk,
                    modality="CT",
                    body_part="CHEST",
                    study_date_shifted=datetime(2026, 4, 1 + i, tzinfo=UTC).replace(tzinfo=None),
                    n_instances=1,
                    n_series=1,
                    total_bytes=100,
                    central_job_id=f"j{i}",
                    gateway_id="gw",
                )
            )
        session.commit()

        req = SearchRequest(modality=["CT"])
        est = estimate_cost(session, req, max_rows=100, facet_suppress_rows=1000)
        assert est.estimated_rows == 5
        assert est.method in {"count", "explain"}


def test_estimator_with_date_filter(engine) -> None:
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        hospital = Hospital(
            hospital_id="h2", name="h", salt_version_current=1, allowed_ruleset_versions=["v0.1.0"]
        )
        session.add(hospital)
        session.flush()
        for i in range(10):
            session.add(
                Study(
                    pseudo_study_uid=f"uid2_{i}",
                    hospital_pk=hospital.hospital_pk,
                    modality="CT",
                    study_date_shifted=datetime(2026, 1, 1 + i, tzinfo=UTC).replace(tzinfo=None),
                    n_instances=1,
                    n_series=1,
                    total_bytes=100,
                    central_job_id=f"j{i}",
                    gateway_id="gw",
                )
            )
        session.commit()

        req = SearchRequest(
            modality=["CT"],
            study_date_shifted=StudyDateRange.model_validate(
                {"from": "2026-01-01", "to": "2026-01-06"}
            ),
        )
        est = estimate_cost(session, req, max_rows=100, facet_suppress_rows=1000)
        # Half-open range [from, to) → 5 days matched.
        assert est.estimated_rows == 5
