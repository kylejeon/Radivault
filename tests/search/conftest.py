"""Shared fixtures for radivault_search tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: F401

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from radivault_central.db.models import Base as CentralBase
from radivault_central.db.models import Hospital, PatientPseudo, Study
from radivault_search.app import create_app
from radivault_search.auth.buyer_tokens import generate_buyer_key
from radivault_search.config import Settings
from radivault_search.db.models import Buyer, BuyerApiKey
from radivault_search.db.session import get_engine, reset_for_tests


@pytest.fixture
def settings() -> Settings:
    s = Settings()
    s.app.env = "test"
    s.db.dsn = "sqlite+pysqlite:///:memory:"
    s.db.admin_dsn = s.db.dsn
    s.db.migration_dsn = s.db.dsn
    s.observability.log_level = "WARNING"
    s.redis.auth_cache_ttl_seconds = 2
    s.auth.global_filter_salt = "test_salt"
    # Lower the cost cap so we can trigger ERR_QUERY_TOO_BROAD with synthetic DBs.
    s.cost.max_estimated_rows = 1000
    s.cost.facet_auto_suppress_rows = 500
    return s


@pytest.fixture
def engine_and_factory(settings: Settings):
    reset_for_tests()
    engine = get_engine(settings.db.dsn, pool_size=2, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    factory: sessionmaker[Session] = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine, factory
    engine.dispose()
    reset_for_tests()


@pytest.fixture
def seeded_buyer(engine_and_factory):
    _, factory = engine_and_factory
    bundle = generate_buyer_key()
    with factory() as session:
        buyer = Buyer(
            buyer_id="buy_test_001",
            name="Test Buyer",
            contact_email="test@example.com",
            tier="paid",
            active=True,
            scope_json={},
        )
        session.add(buyer)
        session.flush()
        key = BuyerApiKey(
            buyer_pk=buyer.buyer_pk,
            kid=bundle.kid,
            token_hash=bundle.hash,
            tier="paid",
            scope_json={},
        )
        session.add(key)
        session.commit()
        session.refresh(buyer)
    return buyer, bundle


@pytest.fixture
def synthetic_studies(engine_and_factory):
    """Seed N synthetic study rows for paging/facet tests."""
    _, factory = engine_and_factory

    modalities = ["CT", "MR", "CR"]
    body_parts = ["CHEST", "ABDOMEN", "HEAD"]
    manufacturers = ["SIEMENS", "GE", "PHILIPS"]
    sexes = ["M", "F"]

    N = 120  # enough for multi-page keyset testing
    with factory() as session:
        hospital = Hospital(
            hospital_id="hosp_syn",
            name="Synthetic Hospital",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
        )
        session.add(hospital)
        session.flush()
        pp = PatientPseudo(
            hospital_pk=hospital.hospital_pk,
            pseudo_patient_key="syn_p1",
            age_bucket=60,
            sex="M",
        )
        session.add(pp)
        session.flush()

        start = datetime(2024, 1, 1, tzinfo=UTC)
        rows = []
        for i in range(N):
            date_i = start + timedelta(days=i)
            rows.append(
                Study(
                    pseudo_study_uid=f"2.25.syn.{i:06d}",
                    hospital_pk=hospital.hospital_pk,
                    patient_pseudo_pk=pp.patient_pseudo_pk,
                    modality=modalities[i % len(modalities)],
                    body_part=body_parts[i % len(body_parts)],
                    study_date_shifted=date_i.replace(tzinfo=None),
                    manufacturer=manufacturers[i % len(manufacturers)],
                    model_name=f"model_{i % 4}",
                    n_instances=10 + (i % 5),
                    n_series=1 + (i % 3),
                    total_bytes=1024 * (i + 1),
                    central_job_id=f"job_{i:06d}",
                    gateway_id="gw_test",
                )
            )
        session.add_all(rows)
        session.commit()
    _ = sexes  # unused but retained for future filter cases
    return hospital, N


@pytest.fixture
def app_client(settings: Settings, engine_and_factory, seeded_buyer) -> Iterator[TestClient]:
    """Build a TestClient sharing the in-memory engine + fakeredis.

    ``testing=True`` makes ``create_app`` reuse the cached singleton engine
    (seeded by the ``engine_and_factory`` fixture) and wire a fakeredis.
    """
    app = create_app(settings, testing=True)
    with TestClient(app) as client:
        yield client
