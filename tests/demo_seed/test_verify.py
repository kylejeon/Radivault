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
    routes = {
        ("POST", "/v1/search/studies"): httpx.Response(200, json={"total": 412, "items": []}),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_studies=300)
    r = verify_mod.check_v2_search_total(ctx)
    assert r.ok
    assert "412" in r.detail


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
    routes = {
        ("GET", "/v1/search/facets"): httpx.Response(
            200, json={"modality": [{"value": "CT", "count": 100}, {"value": "MR", "count": 50}, {"value": "MG", "count": 20}]}
        ),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_modalities=3)
    r = verify_mod.check_v3_modality_facet(ctx)
    assert r.ok


def test_v3_modality_facet_fail(verify_mod):
    Session = _mk_in_memory_session()
    routes = {
        ("GET", "/v1/search/facets"): httpx.Response(200, json={"modality": [{"value": "CT", "count": 1}]}),
    }
    ctx = _ctx(verify_mod, Session, http_handler=_build_http_handler(routes), min_modalities=3)
    r = verify_mod.check_v3_modality_facet(ctx)
    assert not r.ok


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
