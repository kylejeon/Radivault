"""ingest-admin CLI smoke tests."""

from __future__ import annotations

from click.testing import CliRunner

from radivault_central.db.session import reset_for_tests
from radivault_central_admin.cli import cli


def test_help_lists_nine_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # The command groups documented in design-spec §3.2.
    for group in ["token", "anchor", "study", "withdraw", "migrate", "version", "init-hospital"]:
        assert group in result.output


def test_version_emits_json(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["version", "--json"])
    assert result.exit_code == 0
    assert "radivault-central" in result.output
    assert "\"version\"" in result.output


def test_token_issue_requires_hospital(tmp_path, monkeypatch):
    monkeypatch.delenv("RV_CENTRAL_CONFIG", raising=False)
    monkeypatch.delenv("RADIVAULT_CENTRAL_CONFIG", raising=False)
    db_url = f"sqlite+pysqlite:///{tmp_path / 'admin.db'}"
    reset_for_tests()
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--database-url", db_url, "token", "issue", "--hospital-id", "nope"],
    )
    assert result.exit_code == 1
    assert "ERR_ADMIN_HOSPITAL_NOT_FOUND" in result.output


def test_init_hospital_then_token_issue(tmp_path):
    reset_for_tests()
    db_url = f"sqlite+pysqlite:///{tmp_path / 'admin.db'}"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--database-url",
            db_url,
            "init-hospital",
            "--hospital-id",
            "hosp_ok",
            "--name",
            "Ok Hosp",
        ],
    )
    assert result.exit_code == 0
    result = runner.invoke(
        cli,
        [
            "--database-url",
            db_url,
            "token",
            "issue",
            "--hospital-id",
            "hosp_ok",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert "plaintext" in result.output

    # list shows that token
    result = runner.invoke(cli, ["--database-url", db_url, "token", "list", "--json"])
    assert result.exit_code == 0
    assert "hosp_ok" in result.output
