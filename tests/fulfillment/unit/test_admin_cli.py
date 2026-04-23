"""fulfillment-admin CLI smoke tests."""

from __future__ import annotations

import json

from click.testing import CliRunner

from radivault_fulfillment_admin.cli import cli


def test_version_json():
    runner = CliRunner()
    res = runner.invoke(cli, ["version", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["service"] == "radivault-fulfillment"


def test_help_lists_command_tree():
    runner = CliRunner()
    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    out = res.output
    for group in ("order", "transfer-job", "dlq", "download", "unlinked", "migrate"):
        assert group in out


def test_subcommand_inventory_size():
    """FR-85 — ≥20 subcommands total."""

    def enumerate_all(group, prefix=""):
        cmds = []
        for name, c in group.commands.items():
            full = f"{prefix}{name}"
            if hasattr(c, "commands"):
                cmds.extend(enumerate_all(c, prefix=f"{full} "))
            else:
                cmds.append(full)
        return cmds

    total = len(enumerate_all(cli))
    assert total >= 20, f"only {total} subcommands registered"


def test_order_inspect_not_found(tmp_path, monkeypatch):
    """Exit code 65 (EX_DATAERR) on missing order."""
    from radivault_fulfillment.db.session import reset_for_tests

    reset_for_tests()
    # Ask admin CLI to use a fresh SQLite DB.
    db_url = f"sqlite+pysqlite:///{tmp_path}/admin_test.db"
    monkeypatch.setenv("FULFILLMENT_ADMIN_DSN", db_url)
    # Create tables up front (no alembic for a smoke test).
    from sqlalchemy import create_engine

    import radivault_fulfillment.db.models  # noqa: F401
    import radivault_search.db.models  # noqa: F401
    from radivault_central.db.models import Base as CentralBase

    engine = create_engine(db_url)
    CentralBase.metadata.create_all(engine)
    engine.dispose()

    runner = CliRunner()
    res = runner.invoke(cli, ["order", "inspect", "--order-id", "ord_missing"])
    assert res.exit_code == 65
    reset_for_tests()
