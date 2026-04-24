"""Unit tests for scripts/demo_seed/seed_hospital.py."""

from __future__ import annotations

import json

import pytest


class FakeCompleted:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_ensure_hospital_enrolled(hospital_mod, monkeypatch):
    monkeypatch.setattr(
        hospital_mod,
        "_run",
        lambda cmd: FakeCompleted(returncode=0, stdout="[OK] enrolled HOSP-001\n"),
    )
    assert hospital_mod.ensure_hospital(["docker", "exec", "c"], "HOSP-001", "Demo") == "enrolled"


def test_ensure_hospital_exists(hospital_mod, monkeypatch):
    monkeypatch.setattr(
        hospital_mod,
        "_run",
        lambda cmd: FakeCompleted(returncode=0, stdout="[EXISTS] HOSP-001\n"),
    )
    assert hospital_mod.ensure_hospital(["docker", "exec", "c"], "HOSP-001", "Demo") == "exists"


def test_ensure_hospital_fail(hospital_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        hospital_mod,
        "_run",
        lambda cmd: FakeCompleted(returncode=1, stderr="permission denied"),
    )
    with pytest.raises(SystemExit) as exc:
        hospital_mod.ensure_hospital(["docker", "exec", "c"], "HOSP-001", "Demo")
    assert exc.value.code == 4
    assert "ERR_SEED_HOSPITAL_INIT_FAILED" in capsys.readouterr().err


def test_issue_admin_token(hospital_mod, monkeypatch):
    payload = {
        "hospital_id": "HOSP-001",
        "kid": "rvct_test",
        "plaintext": "rvct_test.secret",
        "expires_at": None,
        "note": "seed",
    }
    monkeypatch.setattr(
        hospital_mod,
        "_run",
        lambda cmd: FakeCompleted(returncode=0, stdout=json.dumps(payload)),
    )
    out = hospital_mod.issue_admin_token(["docker", "exec", "c"], "HOSP-001", "seed")
    assert out["plaintext"] == "rvct_test.secret"


def test_main_no_token_by_default(hospital_mod, monkeypatch, capsys):
    """Without --issue-token we must NOT issue a token (dev-spec 'do not touch .env.local')."""
    calls: list[list[str]] = []

    def fake_run(cmd):
        calls.append(cmd)
        if "init-hospital" in cmd:
            return FakeCompleted(returncode=0, stdout="[EXISTS] HOSP-001\n")
        # Anything else is a test bug.
        raise AssertionError(f"unexpected cmd: {cmd}")

    monkeypatch.setattr(hospital_mod, "_run", fake_run)
    monkeypatch.setattr(hospital_mod.shutil, "which", lambda _n: "/usr/bin/docker")

    rc = hospital_mod.main(["--hospital-id", "HOSP-001"])
    assert rc == 0
    assert "[OK] hospital HOSP-001 ready" in capsys.readouterr().out
    # Only the init-hospital call, not token issue.
    assert any("init-hospital" in c for c in calls)
    assert not any("token" in c and "issue" in c for c in calls)


def test_main_with_issue_token_prints_bearer(hospital_mod, monkeypatch, capsys):
    payload = {
        "hospital_id": "HOSP-001",
        "kid": "rvct_issued",
        "plaintext": "rvct_issued.abcdef",
        "expires_at": None,
        "note": "demo",
    }

    def fake_run(cmd):
        if "init-hospital" in cmd:
            return FakeCompleted(returncode=0, stdout="[EXISTS] HOSP-001\n")
        if "token" in cmd and "issue" in cmd:
            return FakeCompleted(returncode=0, stdout=json.dumps(payload))
        raise AssertionError(f"unexpected cmd: {cmd}")

    monkeypatch.setattr(hospital_mod, "_run", fake_run)
    monkeypatch.setattr(hospital_mod.shutil, "which", lambda _n: "/usr/bin/docker")

    rc = hospital_mod.main(["--issue-token"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "HOSPITAL_UPSTREAM_BEARER=rvct_issued.abcdef" in out
