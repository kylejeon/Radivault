"""Integration tests for Hospital Dashboard endpoints (D-2 / D-4).

Tests target:

* ``GET /v1/hospital/me/stats`` — studies today/cumulative, modality distribution,
  monthly 12m bucket, gateway health derivation.
* ``GET /v1/hospital/me/gateway-health`` — status label mapping.
* ``GET /v1/hospital/me/audit`` — whitelisted event stream.

Auth is via the existing hospital bearer token (central-ingest ``auth_token``
row). Reuses the file-backed SQLite pattern from ``test_ingest_audit_rejection``
so the app-internal session factory and the test-side factory share state.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from radivault_central.app import create_app
from radivault_central.auth.tokens import generate_token
from radivault_central.config import Settings
from radivault_central.db.models import (
    AuditIngestEvent,
    AuthToken,
    Base,
    Hospital,
    Study,
)
from radivault_central.db.session import get_engine, reset_for_tests
from radivault_central.storage.local import LocalFsObjectStore


@pytest.fixture
def portal_app(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, str, str, sessionmaker]]:
    """File-backed SQLite so router-side and test-side see the same rows."""
    reset_for_tests()
    db_path = tmp_path / "central.db"
    settings = Settings()
    settings.app.env = "test"
    settings.db.dsn = f"sqlite+pysqlite:///{db_path}"
    settings.storage.provider = "local"
    settings.storage.local_root = str(tmp_path / "store")
    settings.observability.log_level = "WARNING"

    engine = get_engine(settings.db.dsn, pool_size=2, max_overflow=0)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        hospital = Hospital(
            hospital_id="hosp_seoul",
            name="Seoul Dashboard Hospital",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
        )
        session.add(hospital)
        session.flush()
        bundle = generate_token()
        session.add(
            AuthToken(
                hospital_pk=hospital.hospital_pk,
                token_kid=bundle.kid,
                token_hash=bundle.hash,
            )
        )
        # A second hospital to confirm scope isolation.
        other = Hospital(
            hospital_id="hosp_other",
            name="Other Hospital",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
        )
        session.add(other)
        session.flush()
        other_bundle = generate_token()
        session.add(
            AuthToken(
                hospital_pk=other.hospital_pk,
                token_kid=other_bundle.kid,
                token_hash=other_bundle.hash,
            )
        )
        session.commit()
    engine.dispose()
    reset_for_tests()

    app = create_app(settings, testing=False)
    app.state.redis = FakeStrictRedis()
    app.state.object_store = LocalFsObjectStore(settings.storage.local_root)
    for m in app.user_middleware:
        if m.cls.__name__ in {"IdempotencyMiddleware", "RateLimitMiddleware"}:
            m.kwargs["redis_client"] = app.state.redis

    with TestClient(app) as client:
        yield client, bundle.plaintext, other_bundle.plaintext, app.state.session_factory


def _seed_studies(factory: sessionmaker, hospital_id: str, counts: dict[str, int]):
    """Add (modality -> count) studies for the given hospital. Timestamps 'today'."""
    now = datetime.now(tz=UTC)
    with factory() as session:
        hospital = session.query(Hospital).filter_by(hospital_id=hospital_id).one()
        idx = 0
        for modality, n in counts.items():
            for _ in range(n):
                idx += 1
                session.add(
                    Study(
                        pseudo_study_uid=f"2.25.{hospital_id}.{idx}",
                        hospital_pk=hospital.hospital_pk,
                        modality=modality,
                        n_instances=2,
                        n_series=1,
                        total_bytes=1024,
                        central_job_id=f"ingest_{idx:08x}",
                        gateway_id="gw_demo_01",
                        ingested_at=now,
                    )
                )
        session.commit()


def _seed_audit(factory: sessionmaker, hospital_id: str, events: list[tuple[str, str | None]]):
    with factory() as session:
        hospital = session.query(Hospital).filter_by(hospital_id=hospital_id).one()
        for i, (event, err) in enumerate(events):
            session.add(
                AuditIngestEvent(
                    hospital_pk=hospital.hospital_pk,
                    gateway_id="gw_demo_01",
                    central_job_id=f"ingest_{i:08x}",
                    event=event,
                    status_code=200 if err is None else 400,
                    error_code=err,
                    request_id=f"rid_{i:08x}",
                )
            )
        session.commit()


# ---------------------------------------------------------------------------
# /v1/hospital/me/stats
# ---------------------------------------------------------------------------
def test_stats_returns_envelope_with_counts(portal_app):
    client, token, _, factory = portal_app
    _seed_studies(factory, "hosp_seoul", {"CT": 3, "MR": 2})

    resp = client.get(
        "/v1/hospital/me/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    data = body["data"]
    assert data["hospital_id"] == "hosp_seoul"
    assert data["studies"]["today"] == 5
    assert data["studies"]["cumulative"] == 5
    # 12 month buckets
    assert len(data["studies"]["monthly_12m"]) == 12
    modalities = {m["modality"]: m["count"] for m in data["modality_distribution"]}
    assert modalities == {"CT": 3, "MR": 2}
    assert data["gateway_health"]["status"] == "online"


def test_stats_auth_missing_returns_401(portal_app):
    client, _, _, _ = portal_app
    resp = client.get("/v1/hospital/me/stats")
    assert resp.status_code == 401
    assert resp.json()["error"] == "ERR_AUTH_MISSING"


def test_stats_invalid_token_returns_401(portal_app):
    client, _, _, _ = portal_app
    resp = client.get(
        "/v1/hospital/me/stats",
        headers={"Authorization": "Bearer rvct_deadbeef.irrelevant"},
    )
    assert resp.status_code == 401


def test_stats_scope_isolation_between_hospitals(portal_app):
    client, token_a, token_b, factory = portal_app
    _seed_studies(factory, "hosp_seoul", {"CT": 5})
    _seed_studies(factory, "hosp_other", {"CT": 11})

    a = client.get("/v1/hospital/me/stats", headers={"Authorization": f"Bearer {token_a}"}).json()
    b = client.get("/v1/hospital/me/stats", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert a["data"]["hospital_id"] == "hosp_seoul"
    assert a["data"]["studies"]["cumulative"] == 5
    assert b["data"]["hospital_id"] == "hosp_other"
    assert b["data"]["studies"]["cumulative"] == 11


def test_stats_period_today_shrinks_monthly_series(portal_app):
    client, token, _, factory = portal_app
    _seed_studies(factory, "hosp_seoul", {"CT": 1})

    resp = client.get(
        "/v1/hospital/me/stats?period=today",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert len(body["studies"]["monthly_12m"]) == 1


def test_stats_empty_hospital_returns_zero_counts(portal_app):
    client, token, _, _ = portal_app
    resp = client.get(
        "/v1/hospital/me/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["studies"]["today"] == 0
    assert data["studies"]["cumulative"] == 0
    assert data["modality_distribution"] == []
    # No study rows ⇒ "unknown" health.
    assert data["gateway_health"]["status"] == "unknown"


# ---------------------------------------------------------------------------
# /v1/hospital/me/gateway-health
# ---------------------------------------------------------------------------
def test_gateway_health_online_under_5min(portal_app):
    client, token, _, factory = portal_app
    _seed_studies(factory, "hosp_seoul", {"CT": 1})
    resp = client.get(
        "/v1/hospital/me/gateway-health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "online"
    assert body["gateway_id"] == "gw_demo_01"
    assert body["last_sync_delta_seconds"] is not None
    assert body["last_sync_delta_seconds"] < 5


def test_gateway_health_warning_label_for_stale_ingest(portal_app):
    client, token, _, factory = portal_app
    # Directly insert a stale study.
    stale = datetime.now(tz=UTC) - timedelta(minutes=10)
    with factory() as session:
        hospital = session.query(Hospital).filter_by(hospital_id="hosp_seoul").one()
        session.add(
            Study(
                pseudo_study_uid="2.25.stale.1",
                hospital_pk=hospital.hospital_pk,
                modality="CT",
                n_instances=1,
                n_series=1,
                total_bytes=1024,
                central_job_id="ingest_stale",
                gateway_id="gw_demo_01",
                ingested_at=stale,
            )
        )
        session.commit()
    resp = client.get(
        "/v1/hospital/me/gateway-health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "warning"


def test_gateway_health_offline_label_for_very_stale_ingest(portal_app):
    client, token, _, factory = portal_app
    stale = datetime.now(tz=UTC) - timedelta(hours=2)
    with factory() as session:
        hospital = session.query(Hospital).filter_by(hospital_id="hosp_seoul").one()
        session.add(
            Study(
                pseudo_study_uid="2.25.veryolddata.1",
                hospital_pk=hospital.hospital_pk,
                modality="CT",
                n_instances=1,
                n_series=1,
                total_bytes=1024,
                central_job_id="ingest_old",
                gateway_id="gw_demo_01",
                ingested_at=stale,
            )
        )
        session.commit()
    resp = client.get(
        "/v1/hospital/me/gateway-health",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()["data"]
    assert body["status"] == "offline"


def test_gateway_health_unknown_when_no_studies(portal_app):
    client, token, _, _ = portal_app
    resp = client.get(
        "/v1/hospital/me/gateway-health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "unknown"
    assert body["gateway_id"] is None


# ---------------------------------------------------------------------------
# /v1/hospital/me/audit
# ---------------------------------------------------------------------------
def test_audit_events_whitelisted_only(portal_app):
    client, token, _, factory = portal_app
    _seed_audit(
        factory,
        "hosp_seoul",
        [
            ("ingest.accepted", None),
            ("ingest.rejected", "ERR_MANIFEST_ANON"),
            ("anchor.recorded", None),
            ("private.internal", None),  # must be filtered out
        ],
    )
    resp = client.get(
        "/v1/hospital/me/audit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    events = resp.json()["data"]["events"]
    event_types = {e["event_type"] for e in events}
    assert "private.internal" not in event_types
    assert "ingest.accepted" in event_types
    for e in events:
        # hash_short is 1-8 chars, alphanumeric, lowercase.
        assert 1 <= len(e["hash_short"]) <= 8
        assert e["hash_short"].isalnum()


def test_audit_respects_limit_query(portal_app):
    client, token, _, factory = portal_app
    _seed_audit(factory, "hosp_seoul", [("ingest.accepted", None)] * 20)
    resp = client.get(
        "/v1/hospital/me/audit?limit=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["events"]) == 5


def test_audit_limit_clamped_to_valid_range(portal_app):
    client, token, _, _ = portal_app
    # limit=0 → pydantic 422 (coerced via our envelope).
    resp = client.get(
        "/v1/hospital/me/audit?limit=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (400, 422)


def test_audit_hospital_scope_isolation(portal_app):
    client, token_a, token_b, factory = portal_app
    _seed_audit(factory, "hosp_seoul", [("ingest.accepted", None)] * 3)
    _seed_audit(factory, "hosp_other", [("ingest.accepted", None)] * 7)
    resp_a = client.get(
        "/v1/hospital/me/audit",
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()
    resp_b = client.get(
        "/v1/hospital/me/audit",
        headers={"Authorization": f"Bearer {token_b}"},
    ).json()
    assert len(resp_a["data"]["events"]) == 3
    assert len(resp_b["data"]["events"]) == 7


def test_audit_excludes_phi_columns(portal_app):
    """No PHI-adjacent fields (PatientName/PatientID/StudyInstanceUID) should
    ever appear in the audit payload — the projection only exposes
    ts/event_type/hash_short/detail_code."""
    client, token, _, factory = portal_app
    _seed_audit(factory, "hosp_seoul", [("ingest.accepted", None)])
    resp = client.get(
        "/v1/hospital/me/audit",
        headers={"Authorization": f"Bearer {token}"},
    )
    body_text = resp.text
    for forbidden in (
        "PatientName",
        "PatientID",
        "StudyInstanceUID",
        "PatientBirthDate",
        "HONG^GILDONG",
    ):
        assert forbidden not in body_text
