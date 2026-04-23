"""Shared fixtures for radivault_fulfillment tests.

SQLite :memory: + fakeredis — mirrors the ``tests/search/conftest.py``
pattern so the full stack (central models + search models + fulfilment
models) is available on one metadata object.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path  # noqa: F401

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from radivault_central.auth.tokens import generate_token
from radivault_central.db.models import (
    AuthToken,
    Hospital,
    Instance,
    PatientPseudo,
    Series,
    Study,
)
from radivault_central.db.models import Base as CentralBase
from radivault_fulfillment.app import create_app
from radivault_fulfillment.config import Settings
from radivault_fulfillment.db.session import get_engine, reset_for_tests
from radivault_search.auth.buyer_tokens import generate_buyer_key
from radivault_search.db.models import Buyer, BuyerApiKey

AGREEMENT_HASH = hashlib.sha256(b"MSA v0.1 fulfilment test").hexdigest()


@pytest.fixture
def settings() -> Settings:
    s = Settings()
    s.app.env = "test"
    s.db.dsn = "sqlite+pysqlite:///:memory:"
    s.db.admin_dsn = s.db.dsn
    s.observability.log_level = "WARNING"
    s.redis.auth_cache_ttl_seconds = 2
    s.audit.agreement_hash_current = AGREEMENT_HASH
    s.order.estimated_ready_seconds_per_study_hot = 0.5
    s.order.estimated_ready_seconds_per_study_cold = 36.0
    # Tight caps so tests can trigger edges with minimal data.
    s.order.tier_preview.max_cohort_size = 3
    s.order.tier_preview.max_order_bytes = 10 * 1024 * 1024  # 10 MB
    s.order.tier_preview.daily_order_quota = 2
    s.order.tier_preview.download_ttl_max_seconds = 86400
    s.order.tier_preview.unit_price_usd = 5.0
    s.order.tier_paid.max_cohort_size = 100
    s.order.tier_paid.max_order_bytes = 100 * 1024 * 1024
    s.order.tier_paid.daily_order_quota = 50
    s.order.tier_paid.download_ttl_max_seconds = 604_800
    s.order.tier_paid.unit_price_usd = 5.0
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
def seeded_hospital(engine_and_factory):
    _, factory = engine_and_factory
    with factory() as session:
        hospital = Hospital(
            hospital_id="hosp_abc",
            name="Test Hospital",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
        )
        session.add(hospital)
        session.flush()
        bundle = generate_token()
        token = AuthToken(
            hospital_pk=hospital.hospital_pk,
            token_kid=bundle.kid,
            token_hash=bundle.hash,
        )
        session.add(token)
        session.commit()
        session.refresh(hospital)
    return hospital, bundle


@pytest.fixture
def seeded_buyer(engine_and_factory):
    _, factory = engine_and_factory
    bundle = generate_buyer_key()
    with factory() as session:
        buyer = Buyer(
            buyer_id="buy_test_001",
            name="Test Buyer",
            contact_email="buyer@example.com",
            tier="preview",
            active=True,
            scope_json={},
        )
        session.add(buyer)
        session.flush()
        key = BuyerApiKey(
            buyer_pk=buyer.buyer_pk,
            kid=bundle.kid,
            token_hash=bundle.hash,
            tier="preview",
            scope_json={},
        )
        session.add(key)
        session.commit()
        session.refresh(buyer)
    return buyer, bundle


@pytest.fixture
def seeded_studies(engine_and_factory, seeded_hospital):
    """Create 5 studies + series + instances for a hospital."""
    _, factory = engine_and_factory
    hospital, _ = seeded_hospital
    uids: list[str] = []
    with factory() as session:
        pp = PatientPseudo(
            hospital_pk=hospital.hospital_pk,
            pseudo_patient_key="pseudo_patient_1",
            age_bucket=60,
            sex="M",
        )
        session.add(pp)
        session.flush()
        for i in range(5):
            uid = f"2.25.test.{i:05d}"
            uids.append(uid)
            study = Study(
                pseudo_study_uid=uid,
                hospital_pk=hospital.hospital_pk,
                patient_pseudo_pk=pp.patient_pseudo_pk,
                modality="CT",
                body_part="CHEST",
                study_date_shifted=datetime(2024, 1, 1 + i).replace(tzinfo=None),
                n_instances=2,
                n_series=1,
                total_bytes=1024 * 512,  # 512 KB each
                central_job_id=f"job_{i}",
                gateway_id="gw_test",
                central_object_present=False,
            )
            session.add(study)
            session.flush()
            series = Series(
                study_pk=study.study_pk,
                pseudo_series_uid=f"{uid}.series.1",
                modality="CT",
                body_part="CHEST",
                series_number=1,
                n_instances=2,
            )
            session.add(series)
            session.flush()
            for j in range(2):
                inst = Instance(
                    series_pk=series.series_pk,
                    pseudo_sop_uid=f"{uid}.inst.{j}",
                    sop_class_uid="1.2.840.10008.5.1.4.1.1.2",
                    instance_number=j + 1,
                    object_key=f"ingest/aa/{hospital.hospital_id}/{uid}/inst_{j}.dcm",
                    bytes=256 * 1024,
                    sha256=hashlib.sha256(f"{uid}-{j}".encode()).digest(),
                )
                session.add(inst)
        session.commit()
    return uids


@pytest.fixture
def app_client(
    settings: Settings, engine_and_factory, seeded_buyer, seeded_hospital
) -> Iterator[TestClient]:
    app = create_app(settings, testing=True)
    with TestClient(app) as client:
        yield client
