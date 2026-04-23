"""Audit writer unit test."""

from __future__ import annotations

import pytest

from radivault_central.db.models import Base as CentralBase
from radivault_search.audit.search_event import write_audit
from radivault_search.db.models import Buyer, SearchAudit
from radivault_search.db.session import get_engine, reset_for_tests


@pytest.fixture
def factory():
    reset_for_tests()
    engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=1, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    f = sessionmaker(bind=engine, expire_on_commit=False)
    # seed buyer
    with f() as session:
        b = Buyer(buyer_id="b1", name="b", contact_email="e@e", tier="paid", scope_json={})
        session.add(b)
        session.commit()
    yield f
    engine.dispose()
    reset_for_tests()


def test_write_audit_inserts_row(factory) -> None:
    write_audit(
        factory,
        buyer_pk=1,
        kid="abcdefab",
        endpoint="/v1/search/studies",
        filter_sha256="a" * 64,
        filter_json_sha256="b" * 64,
        result_count=25,
        cache_hit=False,
        status_code=200,
        error_code=None,
        latency_ms=120,
        request_id="01HXXX-test",
        cursor_presence=False,
    )
    with factory() as session:
        rows = list(session.query(SearchAudit).all())
        assert len(rows) == 1
        r = rows[0]
        assert r.filter_sha256 == "a" * 64
        assert r.status_code == 200
        assert r.result_count == 25


def test_write_audit_swallows_errors(factory, monkeypatch) -> None:
    # Simulate session.commit raising — should not propagate.
    def bad_factory():
        raise RuntimeError("boom")

    write_audit(
        bad_factory,
        buyer_pk=1,
        kid="abcdefab",
        endpoint="/v1/search/studies",
        filter_sha256=None,
        filter_json_sha256=None,
        result_count=0,
        cache_hit=False,
        status_code=500,
        error_code="ERR_INTERNAL",
        latency_ms=1,
        request_id="r",
        cursor_presence=False,
    )
    # No exception = pass.
