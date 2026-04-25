"""Unit tests for scripts/demo_seed/seed_buyer.py.

We patch ``subprocess.run`` (via module attr) so no real ``docker`` /
``search-admin`` calls are made.
"""

from __future__ import annotations

import json

import pytest


class FakeCompleted:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_create_buyer_idempotent_on_duplicate(buyer_mod, monkeypatch):
    """Duplicate buyer_id must not crash — treated as success (idempotent)."""
    monkeypatch.setattr(
        buyer_mod,
        "_run",
        lambda cmd, check=False: FakeCompleted(
            returncode=1,
            stderr="[ERR_ADMIN_BUYER_DUPLICATE] buyer_id already exists: buy_demo001",
        ),
    )
    # Should not raise.
    buyer_mod.create_buyer(
        ["docker", "exec", "c"],
        buyer_id="buy_demo001",
        company="X",
        email="x@y",
        tier="paid",
    )


def test_create_buyer_raises_on_unknown_error(buyer_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        buyer_mod,
        "_run",
        lambda cmd, check=False: FakeCompleted(returncode=1, stderr="connection refused"),
    )
    with pytest.raises(SystemExit) as exc:
        buyer_mod.create_buyer(
            ["docker", "exec", "c"],
            buyer_id="buy_demo001",
            company="X",
            email="x@y",
            tier="paid",
        )
    assert exc.value.code == 4
    assert "ERR_SEED_BUYER_CREATE_FAILED" in capsys.readouterr().err


def test_issue_key_parses_plaintext(buyer_mod, monkeypatch):
    payload = {
        "buyer_id": "buy_demo001",
        "kid": "rv_live_demo0001",
        "plaintext": "rv_live_demo0001.secret",
        "tier": "paid",
        "expires_at": None,
    }
    monkeypatch.setattr(
        buyer_mod,
        "_run",
        lambda cmd, check=False: FakeCompleted(returncode=0, stdout=json.dumps(payload)),
    )
    out = buyer_mod.issue_key(
        ["docker", "exec", "c"],
        buyer_id="buy_demo001",
        tier="paid",
        expires_days=30,
    )
    assert out["plaintext"] == "rv_live_demo0001.secret"


def test_issue_key_raises_without_plaintext_field(buyer_mod, monkeypatch):
    monkeypatch.setattr(
        buyer_mod,
        "_run",
        lambda cmd, check=False: FakeCompleted(
            returncode=0, stdout=json.dumps({"buyer_id": "x", "kid": "y"})
        ),
    )
    with pytest.raises(SystemExit) as exc:
        buyer_mod.issue_key(
            ["docker", "exec", "c"], buyer_id="buy_demo001", tier="paid", expires_days=30
        )
    assert exc.value.code == 7


def test_main_writes_key_file_and_exits_zero(buyer_mod, monkeypatch, tmp_path, capsys):
    """End-to-end main(): should write key file, print banner, return 0."""
    payload = {
        "buyer_id": "buy_demo001",
        "kid": "rv_live_abc12345",
        "plaintext": "rv_live_abc12345.secret-token",
        "tier": "paid",
        "expires_at": "2026-10-21T00:00:00+00:00",
    }

    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        # cmd looks like [..., "search-admin", <group>, <subcmd>, ...flags]
        # Find the (group, subcmd) pair directly after "search-admin".
        try:
            i = cmd.index("search-admin")
            group, sub = cmd[i + 1], cmd[i + 2]
        except (ValueError, IndexError):
            return FakeCompleted(returncode=1, stderr="unexpected cmd")

        if (group, sub) == ("buyer", "show"):
            return FakeCompleted(returncode=1)  # not found → trigger create
        if (group, sub) == ("buyer", "create"):
            return FakeCompleted(returncode=0)
        if (group, sub) == ("key", "issue"):
            return FakeCompleted(returncode=0, stdout=json.dumps(payload))
        return FakeCompleted(returncode=1, stderr=f"unexpected cmd {group}/{sub}")

    monkeypatch.setattr(buyer_mod, "_run", fake_run)
    # Pretend docker is available regardless of host state.
    monkeypatch.setattr(buyer_mod.shutil, "which", lambda _n: "/usr/bin/docker")

    out_path = tmp_path / ".buyer_key.local.txt"
    # --skip-smoke avoids the FR-INF-3 round-trip probe (no live search
    # service in unit tests).
    rc = buyer_mod.main(["--out-path", str(out_path), "--skip-smoke"])
    assert rc == 0
    assert out_path.exists()
    assert out_path.read_text().strip() == payload["plaintext"]
    # File perms should be 0600.
    mode = out_path.stat().st_mode & 0o777
    assert mode == 0o600

    stdout = capsys.readouterr().out
    assert "rv_live_abc12345.secret-token" in stdout
    assert "demo buyer key issued" in stdout


def test_smoke_search_treats_401_as_failure(buyer_mod, monkeypatch):
    """FR-INF-3 contract: a freshly minted key getting 401 means the row
    never landed (e.g. wrong DSN, replication lag) → must surface as fail."""
    import urllib.error

    def fake_urlopen(*a, **kw):
        raise urllib.error.HTTPError(
            url="x", code=401, msg="Unauthorized", hdrs=None, fp=None
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    ok, detail = buyer_mod.smoke_search("rv_live_x.y", "http://search.test")
    assert not ok
    assert "401" in detail


def test_smoke_search_non_401_http_error_is_pass(buyer_mod, monkeypatch):
    """422 / 500 etc. still prove the bearer was accepted — auth layer green."""
    import urllib.error

    def fake_urlopen(*a, **kw):
        raise urllib.error.HTTPError(
            url="x", code=422, msg="Unprocessable", hdrs=None, fp=None
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    ok, detail = buyer_mod.smoke_search("rv_live_x.y", "http://search.test")
    assert ok
    assert "422" in detail


def test_smoke_search_2xx_is_pass(buyer_mod, monkeypatch):
    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: FakeResp())
    ok, detail = buyer_mod.smoke_search("rv_live_x.y", "http://search.test")
    assert ok
    assert "200" in detail


def test_smoke_search_network_failure_is_fail(buyer_mod, monkeypatch):
    def boom(*a, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    ok, detail = buyer_mod.smoke_search("rv_live_x.y", "http://search.test")
    assert not ok
    assert "smoke request failed" in detail


def test_main_skip_when_key_file_exists(buyer_mod, monkeypatch, tmp_path):
    """--skip-if-key-file-exists returns 0 immediately without calling search-admin."""
    out_path = tmp_path / ".buyer_key.local.txt"
    out_path.write_text("rv_live_existing.key\n")

    def boom(*a, **kw):
        raise AssertionError("search-admin should not be called in skip mode")

    monkeypatch.setattr(buyer_mod, "_run", boom)
    rc = buyer_mod.main(
        ["--out-path", str(out_path), "--skip-if-key-file-exists"]
    )
    assert rc == 0
