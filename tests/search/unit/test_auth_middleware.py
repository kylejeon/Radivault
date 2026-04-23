"""Unit tests for ``BuyerAuthMiddleware`` (C-1 defense-in-depth).

FR-6/7 — the middleware updates ``buyer_api_key.last_used_at`` on every
cold-cache auth success. If the DB role lacks UPDATE permission on that
column (e.g., misconfigured GRANT) or the write fails for any other
reason, the request MUST still succeed — we only emit a WARN and continue.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

from radivault_central.db.models import Base as CentralBase
from radivault_search.auth.buyer_tokens import generate_buyer_key
from radivault_search.auth.middleware import BuyerAuthMiddleware
from radivault_search.db.models import Buyer, BuyerApiKey
from radivault_search.db.session import get_engine, reset_for_tests


@pytest.fixture
def app_and_factory():
    reset_for_tests()
    engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=2, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    bundle = generate_buyer_key()
    with factory() as session:
        buyer = Buyer(
            buyer_id="buy_auth_mw_01",
            name="mw test",
            contact_email="t@example.com",
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

    app = FastAPI()

    @app.get("/me")
    async def me(request: Request):
        return {
            "buyer_id": getattr(request.state, "buyer_id", None),
            "tier": getattr(request.state, "tier", None),
        }

    app.add_middleware(
        BuyerAuthMiddleware,
        session_factory=factory,
        redis_client=None,
        auth_cache_ttl_seconds=60,
        allow_test_prefix=True,
    )

    yield app, factory, bundle

    engine.dispose()
    reset_for_tests()


def _swap_session_factory(app: FastAPI, new_factory) -> None:
    for m in app.user_middleware:
        if m.cls.__name__ == "BuyerAuthMiddleware":
            m.kwargs["session_factory"] = new_factory
            return
    raise AssertionError("BuyerAuthMiddleware not found")


class _SessionProxy:
    """Wraps a real Session but overrides ``commit`` with a supplied callable."""

    def __init__(self, real, commit_fn):
        self._real = real
        self._commit_fn = commit_fn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._real.__exit__(*exc)
        return False

    def __getattr__(self, name):
        return getattr(self._real, name)

    def commit(self):
        return self._commit_fn()

    def rollback(self):
        return self._real.rollback()


def test_auth_last_used_update_ok(app_and_factory) -> None:
    """Happy path: UPDATE succeeds, auth returns 200, last_used_at is set."""
    app, factory, bundle = app_and_factory
    with TestClient(app) as client:
        resp = client.get(
            "/me",
            headers={"Authorization": f"Bearer {bundle.plaintext}"},
        )
    assert resp.status_code == 200
    assert resp.json()["buyer_id"] == "buy_auth_mw_01"

    with factory() as session:
        row = session.query(BuyerApiKey).filter_by(kid=bundle.kid).one()
        assert row.last_used_at is not None


def test_auth_last_used_update_permission_denied_soft_fail(app_and_factory, caplog) -> None:
    """C-1: simulated PG ``permission denied`` on UPDATE(last_used_at) must
    NOT fail authentication. Middleware emits ``ERR_LAST_USED_UPDATE_FAILED``
    WARN, auth returns 200."""
    app, real_factory, bundle = app_and_factory

    def _failing_commit():
        raise ProgrammingError(
            statement="UPDATE buyer_api_key SET last_used_at = now()",
            params=None,
            orig=Exception("permission denied for relation buyer_api_key"),
        )

    def _patched_factory():
        return _SessionProxy(real_factory(), _failing_commit)

    _swap_session_factory(app, _patched_factory)

    caplog.set_level(logging.WARNING, logger="radivault_search.auth")
    with TestClient(app) as client:
        resp = client.get(
            "/me",
            headers={"Authorization": f"Bearer {bundle.plaintext}"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["buyer_id"] == "buy_auth_mw_01"
    messages = [r.getMessage() for r in caplog.records]
    assert any("ERR_LAST_USED_UPDATE_FAILED" in m for m in messages), messages


def test_auth_last_used_update_generic_error_soft_fail(app_and_factory) -> None:
    """Any other exception on commit is also soft-failed — auth still 200."""
    app, real_factory, bundle = app_and_factory

    def _raising_commit():
        raise RuntimeError("disk full")

    def _patched_factory():
        return _SessionProxy(real_factory(), _raising_commit)

    _swap_session_factory(app, _patched_factory)

    with TestClient(app) as client:
        resp = client.get(
            "/me",
            headers={"Authorization": f"Bearer {bundle.plaintext}"},
        )
    assert resp.status_code == 200
    assert resp.json()["buyer_id"] == "buy_auth_mw_01"
