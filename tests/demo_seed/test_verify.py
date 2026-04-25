"""Unit tests for scripts/demo_seed/verify.py.

Each V-* checker is tested in isolation using a :class:`VerifyContext`
that injects stubs for the three surfaces the checkers touch:

* ``session_factory``   → SQLAlchemy session (V-1 / V-4 / V-6)
* ``http_factory``      → httpx MockTransport (V-2 / V-3 / V-7 / V-8)
* ``subprocess_runner`` → subprocess.CompletedProcess (V-5)

We avoid standing up a real Postgres by binding to SQLite in-memory
and calling ``Base.metadata.create_all``.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radivault_central.db.models import Base, Hospital, Study


def _mk_in_memory_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed_hospital_and_studies(Session, *, n_studies: int, ingested_at=None, phi: bool = False):
    """Minimal fixture: 1 hospital + n_studies rows."""
    if ingested_at is None:
        ingested_at = datetime.now(tz=UTC)
    with Session() as s:
        h = Hospital(
            hospital_id="HOSP-001",
            name="Demo",
            allowed_ruleset_versions=["v0.1.0"],
            salt_version_current=1,
        )
        s.add(h)
        s.flush()
        for i in range(n_studies):
            raw_tags = {"PatientName": "LEAK"} if phi and i == 0 else {"SOPClassUID": "x"}
            s.add(
                Study(
                    pseudo_study_uid=f"2.25.pseudo.{i}",
                    hospital_pk=h.hospital_pk,
                    modality="CT" if i % 3 == 0 else ("MR" if i % 3 == 1 else "MG"),
                    body_part="CHEST",
                    n_instances=1,
                    n_series=1,
                    total_bytes=1024,
                    central_job_id=f"job-{i}",
                    gateway_id="gw-1",
                    raw_dicom_tags=raw_tags,
                    ingested_at=ingested_at,
                )
            )
        s.commit()


def _ctx(verify_mod, Session, *, http_handler=None, subprocess_handler=None, **kwargs):
    ctx = verify_mod.VerifyContext(
        central_dsn="sqlite+pysqlite:///:memory:",
        search_url="http://search.test",
        central_url="http://central.test",
        hospital_id="HOSP-001",
        hospital_bearer=kwargs.pop("hospital_bearer", "hb-token"),
        buyer_api_key=kwargs.pop("buyer_api_key", "rv_live_demo.key"),
        min_studies=kwargs.pop("min_studies", 5),
        min_modalities=kwargs.pop("min_modalities", 3),
        heartbeat_window_minutes=kwargs.pop("heartbeat_window_minutes", 5),
        session_factory=Session,
    )
    if http_handler is not None:
        transport = httpx.MockTransport(http_handler)
        ctx.http_factory = lambda: httpx.Client(transport=transport)
    if subprocess_handler is not None:
        ctx.subprocess_runner = subprocess_handler
    return ctx


# ---------------------------------------------------------------------------
# V-1
# ---------------------------------------------------------------------------


def test_v1_pass(verify_mod):
    Session = _mk_in_memory_session()
    _seed_hospital_and_studies(Session, n_studies=10)
    r = verify_mod.check_v1_study_count(_ctx(verify_mod, Session, min_studies=5))
    assert r.ok
    assert "10" in r.detail


def test_v1_fail_below_threshold(verify_mod):
    Session = _mk_in_memory_session()
    _seed_hospital_and_studies(Session, n_studies=2)
    r = verify_mod.check_v1_study_count(_ctx(verify_mod, Session, min_studies=5))
    assert not r.ok


# ---------------------------------------------------------------------------
# V-2 / V-3 / V-7 / V-8 — HTTP-backed
# ---------------------------------------------------------------------------


def _build_http_handler(routes: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        for (method, path), response in routes.items():
            if request.method == method and path in str(request.url):
                return response
        return httpx.Response(404)

    return handler


def test_v2_pass(verify_mod):
    Session = _mk_in_memory_session()
    # New SearchResponse shape exposes the hit count via total_count
    # (preferred) or meta.total_hint. Legacy `total` fallback also kept.
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(
            200, json={"total_count": 412, "meta": {"total_hint": 412}, "items": []}
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_studies=300)
    r = verify_mod.check_v2_search_total(ctx)
    assert r.ok
    assert "412" in r.detail


def test_v2_pass_with_meta_total_hint_only(verify_mod):
    """`total_count` may be absent on truncated responses — meta.total_hint
    must still be honoured."""
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(
            200, json={"meta": {"total_hint": 350}, "items": []}
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_studies=300)
    r = verify_mod.check_v2_search_total(ctx)
    assert r.ok
    assert "350" in r.detail


def test_v2_legacy_total_field_still_supported(verify_mod):
    """Drift safety net — old contract used a plain `total` field; the
    fallback chain keeps existing fixtures in callers green."""
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(200, json={"total": 412, "items": []}),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_studies=300)
    r = verify_mod.check_v2_search_total(ctx)
    assert r.ok


def test_v2_fail_on_http_error(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(502),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v2_search_total(ctx)
    assert not r.ok


def test_v3_modality_facet_pass(verify_mod):
    Session = _mk_in_memory_session()
    # FR-INF-3 reroutes V-3 onto POST /v1/search/studies?include_facets=true.
    # Facets live under `facets.modality` (list[FacetValue]) per schema.py.
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(
            200,
            json={
                "items": [],
                "facets": {
                    "modality": [
                        {"value": "CT", "count": 100},
                        {"value": "MR", "count": 50},
                        {"value": "MG", "count": 20},
                    ]
                },
            },
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_modalities=3)
    r = verify_mod.check_v3_modality_facet(ctx)
    assert r.ok


def test_v3_modality_facet_fail(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(
            200,
            json={"items": [], "facets": {"modality": [{"value": "CT", "count": 1}]}},
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_modalities=3)
    r = verify_mod.check_v3_modality_facet(ctx)
    assert not r.ok


def test_v3_handles_empty_facets_block(verify_mod):
    """Defensive: if `facets` is missing entirely (e.g. include_facets=false
    upstream), V-3 must report 0 rather than crash."""
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(200, json={"items": []}),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_modalities=3)
    r = verify_mod.check_v3_modality_facet(ctx)
    assert not r.ok
    assert "0" in r.detail


def test_v7_buyer_search_pass(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(200, json={"total": 10, "items": []}),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v7_buyer_search(ctx)
    assert r.ok


def test_v7_buyer_search_skipped_without_key(verify_mod):
    Session = _mk_in_memory_session()
    ctx = _ctx(verify_mod, Session, buyer_api_key=None)
    r = verify_mod.check_v7_buyer_search(ctx)
    assert not r.ok
    assert "no buyer api key" in r.detail


def test_v8_hospital_stats_pass(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/stats"): httpx.Response(
            200, json={"hospital_id": "HOSP-001", "today": 0, "total": 0}
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v8_hospital_stats(ctx)
    assert r.ok


def test_v8_hospital_stats_fail_on_401(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/stats"): httpx.Response(401),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v8_hospital_stats(ctx)
    assert not r.ok


# ---------------------------------------------------------------------------
# V-4
# ---------------------------------------------------------------------------


def test_v4_heartbeat_within_window(verify_mod):
    Session = _mk_in_memory_session()
    _seed_hospital_and_studies(Session, n_studies=1, ingested_at=datetime.now(tz=UTC))
    r = verify_mod.check_v4_hospital_heartbeat(_ctx(verify_mod, Session, heartbeat_window_minutes=5))
    assert r.ok


def test_v4_heartbeat_stale(verify_mod):
    Session = _mk_in_memory_session()
    stale = datetime.now(tz=UTC) - timedelta(hours=3)
    _seed_hospital_and_studies(Session, n_studies=1, ingested_at=stale)
    r = verify_mod.check_v4_hospital_heartbeat(_ctx(verify_mod, Session, heartbeat_window_minutes=5))
    assert not r.ok


def test_v4_heartbeat_no_studies(verify_mod):
    Session = _mk_in_memory_session()
    # Hospital but no studies yet.
    with Session() as s:
        s.add(
            Hospital(
                hospital_id="HOSP-001",
                name="Demo",
                allowed_ruleset_versions=["v0.1.0"],
                salt_version_current=1,
            )
        )
        s.commit()
    r = verify_mod.check_v4_hospital_heartbeat(_ctx(verify_mod, Session))
    assert not r.ok
    assert "no ingested studies" in r.detail


# ---------------------------------------------------------------------------
# V-5
# ---------------------------------------------------------------------------


def test_v5_anchor_verify_pass(verify_mod):
    Session = _mk_in_memory_session()
    ctx = _ctx(
        verify_mod,
        Session,
        subprocess_handler=lambda cmd: subprocess.CompletedProcess(cmd, 0, "continuity  : PASS", ""),
    )
    r = verify_mod.check_v5_anchor_verify(ctx)
    assert r.ok


def test_v5_anchor_verify_zero_anchors_treated_as_pass(verify_mod):
    Session = _mk_in_memory_session()
    ctx = _ctx(
        verify_mod,
        Session,
        subprocess_handler=lambda cmd: subprocess.CompletedProcess(cmd, 1, "anchors     : 0\n", ""),
    )
    r = verify_mod.check_v5_anchor_verify(ctx)
    assert r.ok
    assert "no anchors yet" in r.detail


def test_v5_anchor_verify_fail(verify_mod):
    Session = _mk_in_memory_session()
    ctx = _ctx(
        verify_mod,
        Session,
        subprocess_handler=lambda cmd: subprocess.CompletedProcess(
            cmd, 1, "", "[FAIL] chain break at seq=42"
        ),
    )
    r = verify_mod.check_v5_anchor_verify(ctx)
    assert not r.ok


# ---------------------------------------------------------------------------
# V-6
# ---------------------------------------------------------------------------


def test_v6_phi_clean(verify_mod):
    Session = _mk_in_memory_session()
    _seed_hospital_and_studies(Session, n_studies=5, phi=False)
    r = verify_mod.check_v6_phi_sampling(_ctx(verify_mod, Session))
    assert r.ok
    assert "PHI suspects = 0" in r.detail


def test_v6_phi_leak_detected(verify_mod):
    Session = _mk_in_memory_session()
    _seed_hospital_and_studies(Session, n_studies=5, phi=True)
    r = verify_mod.check_v6_phi_sampling(_ctx(verify_mod, Session))
    assert not r.ok
    assert "PatientName" in r.detail or "PHI suspects" in r.detail


# ---------------------------------------------------------------------------
# V-9 — federated min_hospitals filter (FR-INF-4)
# ---------------------------------------------------------------------------


def test_v9_min_hospitals_pass_with_items(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(
            200,
            json={
                "items": [{"pseudo_study_uid": "2.25.x", "modality": "CT"}],
                "total_count": 12,
            },
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v9_min_hospitals_filter(ctx)
    assert r.ok
    assert "items=1" in r.detail


def test_v9_min_hospitals_pass_with_total_only(verify_mod):
    """Items may be empty when limit=1 but total_count>0 still proves the
    federated SQL path runs."""
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(
            200, json={"items": [], "total_count": 7}
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v9_min_hospitals_filter(ctx)
    assert r.ok


def test_v9_min_hospitals_fail_when_zero(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(
            200, json={"items": [], "total_count": 0}
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v9_min_hospitals_filter(ctx)
    assert not r.ok


def test_v9_min_hospitals_fail_without_key(verify_mod):
    Session = _mk_in_memory_session()
    ctx = _ctx(verify_mod, Session, buyer_api_key=None)
    r = verify_mod.check_v9_min_hospitals_filter(ctx)
    assert not r.ok


def test_v9_min_hospitals_fail_on_non_200(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(403, json={"error": "forbidden"}),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v9_min_hospitals_filter(ctx)
    assert not r.ok


# ---------------------------------------------------------------------------
# V-11 — hospital audit-chain status (FR-INF-6, HIGH-3 fix)
# ---------------------------------------------------------------------------


def test_v11_audit_chain_status_pass(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/audit-chain-status"): httpx.Response(
            200,
            json={
                "hospital_id": "HOSP-001",
                "last_anchor_at": "2026-04-25T10:00:00Z",
                "hash_prefix": "a3f8d9c1b2e4f5a6",
                "chain_continuous": True,
            },
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v11_audit_chain_status(ctx)
    assert r.ok
    assert "chain_continuous=True" in r.detail


def test_v11_accepts_upstream_field_name(verify_mod):
    """Central uses ``last_anchor_hash_prefix``; the BFF rewrites to
    ``hash_prefix``. V-11 must accept either."""
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/audit-chain-status"): httpx.Response(
            200,
            json={
                "hospital_id": "HOSP-001",
                "last_anchor_at": "2026-04-25T10:00:00Z",
                "last_anchor_hash_prefix": "a3f8d9c1b2e4f5a6",
                "chain_continuous": True,
            },
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v11_audit_chain_status(ctx)
    assert r.ok


def test_v11_fail_on_404_endpoint_missing(verify_mod):
    Session = _mk_in_memory_session()
    routes = {("GET", "/v1/hospital/me/audit-chain-status"): httpx.Response(404)}
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v11_audit_chain_status(ctx)
    assert not r.ok
    assert "not implemented" in r.detail


def test_v11_fail_on_missing_required_fields(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/audit-chain-status"): httpx.Response(
            200, json={"hospital_id": "HOSP-001"}
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v11_audit_chain_status(ctx)
    assert not r.ok
    assert "missing required fields" in r.detail


def test_v11_fail_without_bearer(verify_mod):
    Session = _mk_in_memory_session()
    ctx = _ctx(verify_mod, Session, hospital_bearer=None)
    r = verify_mod.check_v11_audit_chain_status(ctx)
    assert not r.ok
    assert "no hospital bearer" in r.detail


# ---------------------------------------------------------------------------
# V-12 — hospital quota (FR-INF-7, HIGH-3 fix)
# ---------------------------------------------------------------------------


def test_v12_quota_pass_central_shape(verify_mod):
    """Central nests bytes under daily/monthly. V-12 unwraps both."""
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/quota"): httpx.Response(
            200,
            json={
                "hospital_id": "HOSP-001",
                "daily": {
                    "bytes_used": 100,
                    "bytes_limit": 10_000,
                    "resets_at": "2026-04-26T15:00:00Z",
                },
                "monthly": {
                    "bytes_used": 1_000,
                    "bytes_limit": 300_000,
                    "resets_at": "2026-05-01T15:00:00Z",
                },
                "max_concurrent_uploads": 4,
            },
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v12_quota(ctx)
    assert r.ok
    assert "max_concurrent_uploads=4" in r.detail


def test_v12_quota_pass_flat_shape(verify_mod):
    """BFF flattens to top-level *_bytes_used keys; both shapes must pass."""
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/quota"): httpx.Response(
            200,
            json={
                "hospital_id": "HOSP-001",
                "daily_bytes_used": 100,
                "daily_bytes_limit": 10_000,
                "monthly_bytes_used": 1_000,
                "monthly_bytes_limit": 300_000,
                "max_concurrent_uploads": 4,
            },
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v12_quota(ctx)
    assert r.ok


def test_v12_fail_on_404(verify_mod):
    Session = _mk_in_memory_session()
    routes = {("GET", "/v1/hospital/me/quota"): httpx.Response(404)}
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v12_quota(ctx)
    assert not r.ok
    assert "not implemented" in r.detail


def test_v12_fail_on_missing_max_concurrent(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/hospital/me/quota"): httpx.Response(
            200,
            json={
                "hospital_id": "HOSP-001",
                "daily": {"bytes_used": 1, "bytes_limit": 10},
                "monthly": {"bytes_used": 1, "bytes_limit": 10},
            },
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes))
    r = verify_mod.check_v12_quota(ctx)
    assert not r.ok
    assert "max_concurrent_uploads" in r.detail


def test_v12_fail_without_bearer(verify_mod):
    Session = _mk_in_memory_session()
    ctx = _ctx(verify_mod, Session, hospital_bearer=None)
    r = verify_mod.check_v12_quota(ctx)
    assert not r.ok


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def test_format_report_json(verify_mod):
    results = [
        verify_mod.CheckResult("V-1", True, "ok"),
        verify_mod.CheckResult("V-2", False, "nope", hint="try harder"),
    ]
    out = verify_mod.format_report(results, as_json=True)
    data = json.loads(out)
    assert data[0]["ok"] is True
    assert data[1]["hint"] == "try harder"


def test_format_report_text_prints_fail_marker(verify_mod):
    results = [verify_mod.CheckResult("V-1", False, "short", hint="long")]
    out = verify_mod.format_report(results)
    assert "[FAIL] V-1" in out
    assert "hint: long" in out


def test_run_checks_catches_checker_exception(verify_mod, monkeypatch):
    """If a checker raises, run_checks records a FAIL instead of propagating."""

    def boom(_ctx):
        raise RuntimeError("fuse blown")

    monkeypatch.setattr(verify_mod, "CHECKS", [boom])
    Session = _mk_in_memory_session()
    results = verify_mod.run_checks(_ctx(verify_mod, Session))
    assert len(results) == 1
    assert not results[0].ok
    assert "fuse blown" in results[0].detail
