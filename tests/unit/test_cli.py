"""CLI smoke tests using Click's test runner."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from radivault_gateway.cli.main import cli


def _minimal_config(tmp_path: Path) -> Path:
    import yaml

    salt_file = tmp_path / "salt"
    salt_file.write_text("0123456789abcdef" * 2)
    data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
            "hospital_id": "hosp_abc",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": {
            "base_url": "https://pacs.example/dicom-web",
            "auth": {"type": "bearer", "token": "tok"},
            "max_concurrency": 2,
            "poll_interval_seconds": 60,
        },
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt": f"${{file:{salt_file}}}",
            "salt_version": 1,
        },
        "staging": {
            "root": str(tmp_path / "stg"),
            "retention_hours": 72,
            "max_disk_pct": 80,
        },
        "state": {"db_path": str(tmp_path / "state.sqlite3")},
        "audit": {
            "path": str(tmp_path / "audit.log"),
            "anchor_interval_seconds": 3600,
        },
        "central": {
            "base_url": "http://127.0.0.1:0",
            "upload_token": "ct",
            "allow_insecure": True,
        },
        "logging": {"level": "INFO", "json": True},
    }
    p = tmp_path / "gateway.yml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_version_prints_numbers():
    runner = CliRunner()
    r = runner.invoke(cli, ["version"])
    assert r.exit_code == 0
    assert "gateway-agent" in r.output
    assert "0.1.0" in r.output


def test_version_json():
    runner = CliRunner()
    r = runner.invoke(cli, ["version", "--json"])
    assert r.exit_code == 0
    obj = json.loads(r.output.strip())
    assert obj["agent"] == "0.1.0"
    assert obj["ruleset"] == "v0.1.0"


def test_help_lists_commands():
    runner = CliRunner()
    r = runner.invoke(cli, ["--help"])
    assert r.exit_code == 0
    for cmd in ("start", "sync-once", "status", "de-id-test", "audit", "version"):
        assert cmd in r.output


def test_audit_verify_missing_file(tmp_path: Path):
    runner = CliRunner()
    r = runner.invoke(cli, ["audit", "verify", str(tmp_path / "nope.log")])
    assert r.exit_code == 2


def test_audit_verify_ok(tmp_path: Path):
    from radivault_gateway.audit import AuditLogger

    logger = AuditLogger(tmp_path / "audit.log", gateway_id="gw_t")
    logger.append("agent.started")
    logger.append("pacs.query")
    runner = CliRunner()
    r = runner.invoke(cli, ["audit", "verify", str(tmp_path / "audit.log")])
    assert r.exit_code == 0
    assert "PASS" in r.output


def test_de_id_test_happy_path(make_synthetic_study, tmp_path):
    cfg_path = _minimal_config(tmp_path)
    study = make_synthetic_study(n_instances=1)
    dcm = next(study.glob("*.dcm"))
    runner = CliRunner()
    r = runner.invoke(cli, ["-c", str(cfg_path), "de-id-test", str(dcm)])
    assert r.exit_code == 0, r.output
    assert "PASS" in r.output


def test_de_id_test_reports_bad_input(tmp_path):
    cfg_path = _minimal_config(tmp_path)
    bad = tmp_path / "not-dicom.bin"
    bad.write_bytes(b"\x00\x01\x02")
    runner = CliRunner()
    r = runner.invoke(cli, ["-c", str(cfg_path), "de-id-test", str(bad)])
    assert r.exit_code == 1
    assert "ERR_DEID" in r.output


def test_status_shows_stale_row(tmp_path: Path):
    """AC-12 / FR-16: status CLI must surface stale staging entries."""
    import os
    import time

    cfg_path = _minimal_config(tmp_path)
    stg = tmp_path / "stg"
    stg.mkdir(exist_ok=True)
    # Create a fake pseudo-study directory and backdate its mtime so it sits
    # far beyond the 72h retention_hours default used by _minimal_config.
    old_study = stg / "2.25.OLD_STUDY"
    old_study.mkdir()
    ancient = time.time() - (73 * 3600)  # 73 hours ago
    os.utime(old_study, (ancient, ancient))

    runner = CliRunner()
    r = runner.invoke(cli, ["-c", str(cfg_path), "status"])
    assert r.exit_code == 0, r.output
    assert "Stale: 1" in r.output

    # JSON mode carries the same counter.
    r_json = runner.invoke(cli, ["-c", str(cfg_path), "status", "--json"])
    assert r_json.exit_code == 0
    data = json.loads(r_json.output)
    assert data["staging"]["stale_count"] == 1


def test_config_validation_error_exits_64(tmp_path: Path):
    import yaml

    bad = tmp_path / "gateway.yml"
    bad.write_text(yaml.safe_dump({"version": 1}))
    runner = CliRunner()
    r = runner.invoke(cli, ["-c", str(bad), "status"])
    # status loads config → validation error → exit 64
    assert r.exit_code == 64
    assert "ERR_CFG" in r.output
