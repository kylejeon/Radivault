"""Multi-PACS sync — CLI tests (FR-MPS-5).

Covers ``sync-once --pacs <id>`` and ``sync-once --list-pacs`` flag
behaviour, AC-MPS-5 / AC-MPS-6 (per dev-spec).
"""

from __future__ import annotations

# Break the pre-existing circular import.
import radivault_gateway.deid  # noqa: F401

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from radivault_gateway.cli.main import cli


def _multi_pacs_config(tmp_path: Path) -> Path:
    salt_file = tmp_path / "salt"
    salt_file.write_text("0123456789abcdef" * 2)
    data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
            "hospital_id": "HOSP-001",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": [
            {
                "id": "orthanc-a",
                "base_url": "https://a.example/dicom-web",
                "auth": {"type": "bearer", "token": "t1"},
                "priority": 10,
            },
            {
                "id": "orthanc-b",
                "base_url": "https://b.example/dicom-web",
                "auth": {"type": "bearer", "token": "t2"},
                "priority": 20,
                "hospital_id": "HOSP-002",
            },
            {
                "id": "orthanc-disabled",
                "base_url": "https://disabled.example/dicom-web",
                "auth": {"type": "bearer", "token": "t3"},
                "priority": 30,
                "enabled": False,
            },
        ],
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
            "upload_tokens": {"HOSP-001": "tok-a", "HOSP-002": "tok-b"},
            "allow_insecure": True,
        },
        "logging": {"level": "INFO", "json": False, "console_color": "never"},
    }
    p = tmp_path / "gateway.yml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_list_pacs_prints_endpoints_and_exits(tmp_path: Path) -> None:
    cfg_path = _multi_pacs_config(tmp_path)
    runner = CliRunner()
    r = runner.invoke(cli, ["-c", str(cfg_path), "sync-once", "--list-pacs"])
    assert r.exit_code == 0, r.output
    out = r.output
    assert "PACS_ID" in out
    assert "orthanc-a" in out
    assert "orthanc-b" in out
    assert "orthanc-disabled" in out  # disabled rows still listed
    assert "HOSP-001" in out
    assert "HOSP-002" in out


def test_list_pacs_works_with_legacy_single_pacs_config(tmp_path: Path) -> None:
    """``--list-pacs`` against a legacy single-dict pacs config must show
    one row with id='default' (regression for the legacy normaliser)."""
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
            "base_url": "https://legacy.example/dicom-web",
            "auth": {"type": "bearer", "token": "t"},
        },
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt": f"${{file:{salt_file}}}",
            "salt_version": 1,
        },
        "staging": {"root": str(tmp_path / "stg")},
        "state": {"db_path": str(tmp_path / "s.sqlite3")},
        "audit": {"path": str(tmp_path / "audit.log")},
        "central": {
            "base_url": "http://127.0.0.1:0",
            "upload_token": "ct",
            "allow_insecure": True,
        },
    }
    p = tmp_path / "gateway.yml"
    p.write_text(yaml.safe_dump(data))
    runner = CliRunner()
    r = runner.invoke(cli, ["-c", str(p), "sync-once", "--list-pacs"])
    assert r.exit_code == 0, r.output
    assert "default" in r.output
    assert "https://legacy.example/dicom-web" in r.output


def test_sync_once_unknown_pacs_id_exits_64(tmp_path: Path) -> None:
    cfg_path = _multi_pacs_config(tmp_path)
    runner = CliRunner()
    r = runner.invoke(
        cli,
        ["-c", str(cfg_path), "sync-once", "--pacs", "does-not-exist"],
    )
    assert r.exit_code == 64, r.output
    assert "does-not-exist" in r.output


def test_sync_once_filters_by_pacs_id(monkeypatch, tmp_path: Path) -> None:
    """``--pacs orthanc-a`` runs only that endpoint (the orchestrator
    iterates a single-element list). We patch the orchestrator entry
    point so we don't need a live PACS."""
    cfg_path = _multi_pacs_config(tmp_path)
    runner = CliRunner()

    captured: dict = {}

    def fake_run_multi_pacs_once(cfg, **kwargs):
        captured.update(kwargs)
        from radivault_gateway.orchestrator import MultiPacsRunSummary

        return MultiPacsRunSummary(runs=[])

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.run_multi_pacs_once",
        fake_run_multi_pacs_once,
    )
    r = runner.invoke(
        cli, ["-c", str(cfg_path), "sync-once", "--pacs", "orthanc-a"]
    )
    assert r.exit_code == 0, r.output
    assert captured.get("pacs_filter") == "orthanc-a"


def test_sync_once_default_runs_all_enabled(monkeypatch, tmp_path: Path) -> None:
    cfg_path = _multi_pacs_config(tmp_path)
    runner = CliRunner()
    captured: dict = {}

    def fake_run_multi_pacs_once(cfg, **kwargs):
        captured.update(kwargs)
        # Build a successful summary for both enabled endpoints.
        from radivault_gateway.orchestrator import (
            MultiPacsRunSummary,
            PacsRunResult,
        )
        from radivault_gateway.orchestrator.pipeline import RunSummary

        rs = RunSummary(uploaded=3, total=3)
        return MultiPacsRunSummary(
            runs=[
                PacsRunResult(
                    pacs_id="orthanc-a",
                    hospital_id="HOSP-001",
                    ok=True,
                    summary=rs,
                ),
                PacsRunResult(
                    pacs_id="orthanc-b",
                    hospital_id="HOSP-002",
                    ok=True,
                    summary=rs,
                ),
            ]
        )

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.run_multi_pacs_once",
        fake_run_multi_pacs_once,
    )
    r = runner.invoke(cli, ["-c", str(cfg_path), "sync-once"])
    assert r.exit_code == 0, r.output
    assert captured.get("pacs_filter") is None
    # Output reports both endpoints + run summary.
    assert "[orthanc-a]" in r.output
    assert "[orthanc-b]" in r.output
    assert "pacs_ok=2/2" in r.output


def test_sync_once_partial_failure_exits_2(monkeypatch, tmp_path: Path) -> None:
    """One endpoint orchestrator-level fail → exit 2 (FR-MPS-2)."""
    cfg_path = _multi_pacs_config(tmp_path)
    runner = CliRunner()

    def fake_run_multi_pacs_once(cfg, **kwargs):
        from radivault_gateway.orchestrator import (
            MultiPacsRunSummary,
            PacsRunResult,
        )
        from radivault_gateway.orchestrator.pipeline import RunSummary

        return MultiPacsRunSummary(
            runs=[
                PacsRunResult(
                    pacs_id="orthanc-a",
                    hospital_id="HOSP-001",
                    ok=True,
                    summary=RunSummary(uploaded=2, total=2),
                ),
                PacsRunResult(
                    pacs_id="orthanc-b",
                    hospital_id="HOSP-002",
                    ok=False,
                    error="connection refused",
                ),
            ]
        )

    monkeypatch.setattr(
        "radivault_gateway.orchestrator.run_multi_pacs_once",
        fake_run_multi_pacs_once,
    )
    r = runner.invoke(cli, ["-c", str(cfg_path), "sync-once"])
    assert r.exit_code == 2, r.output
    assert "FAILED" in r.output
    assert "connection refused" in r.output


def test_sync_once_help_lists_new_flags() -> None:
    runner = CliRunner()
    r = runner.invoke(cli, ["sync-once", "--help"])
    assert r.exit_code == 0
    assert "--pacs" in r.output
    assert "--list-pacs" in r.output
