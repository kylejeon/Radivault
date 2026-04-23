"""search-admin CLI smoke tests (FR-56..FR-59)."""

from __future__ import annotations

import json

from click.testing import CliRunner

from radivault_search_admin.cli import cli


def _invoke(*args, env=None):
    runner = CliRunner()
    # Point at an in-memory SQLite for unit tests.
    base_env = {"RV_SEARCH_LOG_LEVEL": "WARNING"}
    if env:
        base_env.update(env)
    return runner.invoke(
        cli,
        ["--database-url", "sqlite+pysqlite:///:memory:", *args],
        env=base_env,
    )


def test_version_subcommand() -> None:
    res = _invoke("version")
    assert res.exit_code == 0
    assert "radivault-search" in res.output


def test_version_json() -> None:
    res = _invoke("version", "--json")
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["service"] == "radivault-search"


def test_help_shows_13_plus_version() -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    for group in ("buyer", "key", "stats", "facet", "migrate", "version"):
        assert group in res.output


def test_key_issue_requires_buyer() -> None:
    res = _invoke("key", "issue", "--buyer-id", "nonexistent")
    assert res.exit_code != 0
    assert "ERR_ADMIN_BUYER_NOT_FOUND" in (res.output + res.stderr)


def test_buyer_create_then_key_issue_then_list() -> None:
    # Using a temp SQLite file so the engine survives across CliRunner invocations.
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        dsn = f"sqlite+pysqlite:///{tmp.name}"
        runner = CliRunner()

        res = runner.invoke(
            cli,
            [
                "--database-url",
                dsn,
                "buyer",
                "create",
                "--company",
                "Acme AI",
                "--contact-email",
                "e@a.com",
                "--tier",
                "paid",
                "--json",
            ],
        )
        assert res.exit_code == 0, res.output
        payload = json.loads(res.output)
        buyer_id = payload["buyer_id"]

        res2 = runner.invoke(
            cli,
            [
                "--database-url",
                dsn,
                "key",
                "issue",
                "--buyer-id",
                buyer_id,
                "--expires-days",
                "30",
                "--json",
            ],
        )
        assert res2.exit_code == 0, res2.output
        key_payload = json.loads(res2.output)
        assert key_payload["plaintext"].startswith("rv_live_")

        res3 = runner.invoke(
            cli,
            ["--database-url", dsn, "key", "list", "--buyer-id", buyer_id, "--json"],
        )
        assert res3.exit_code == 0
        payload3 = json.loads(res3.output)
        assert payload3["count"] == 1
        assert payload3["keys"][0]["status"] == "active"


def test_stats_query_count_requires_buyer() -> None:
    res = _invoke("stats", "query-count", "--buyer-id", "missing", "--since", "2026-01-01")
    assert res.exit_code != 0
