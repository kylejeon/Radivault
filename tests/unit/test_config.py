"""Config loader tests — FR-34..FR-37 + design-spec §4.5."""

from __future__ import annotations

from pathlib import Path

import pytest

from radivault_gateway.config import ConfigError, load_config


def _base_config(**overrides) -> str:
    base = {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
            "hospital_id": "hosp_abc",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": {
            "base_url": "https://pacs.example/dicom-web",
            "auth": {"type": "bearer", "token": "tok"},
            "max_concurrency": 4,
            "poll_interval_seconds": 300,
        },
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt": "0123456789abcdef" * 2,
            "salt_version": 1,
        },
        "staging": {
            "root": "/tmp/staging",
            "retention_hours": 72,
            "max_disk_pct": 80,
        },
        "state": {"db_path": "/tmp/state.sqlite3"},
        "audit": {"path": "/tmp/audit.log", "anchor_interval_seconds": 3600},
        "central": {
            "base_url": "https://ingest.example",
            "upload_token": "central-tok",
        },
        "logging": {"level": "INFO", "json": True},
    }
    for key, value in overrides.items():
        base[key] = value
    return base


def _write_yaml(tmp_path: Path, content: dict) -> Path:
    import yaml

    path = tmp_path / "gateway.yml"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return path


def test_load_config_happy_path(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, _base_config())
    cfg = load_config(path)
    assert cfg.agent.gateway_id == "gw_test"
    assert cfg.pacs.max_concurrency == 4
    assert cfg.deid.salt_version == 1
    assert cfg.logging.json_output is True


def test_missing_required_key_raises_err_cfg_002(tmp_path: Path) -> None:
    data = _base_config()
    del data["pacs"]["base_url"]
    path = _write_yaml(tmp_path, data)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert exc.value.code == "ERR_CFG_002"
    assert "pacs.base_url" in exc.value.format_human()


def test_invalid_type_raises_err_cfg_003(tmp_path: Path) -> None:
    data = _base_config()
    data["pacs"]["max_concurrency"] = "four"
    path = _write_yaml(tmp_path, data)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert exc.value.code == "ERR_CFG_003"


def test_missing_secret_file_raises_err_cfg_010(tmp_path: Path) -> None:
    data = _base_config()
    data["deid"]["salt"] = "${file:/nonexistent/salt-file}"
    path = _write_yaml(tmp_path, data)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert exc.value.code == "ERR_CFG_010"


def test_env_interpolation(tmp_path: Path) -> None:
    data = _base_config()
    data["central"]["upload_token"] = "${env:CUSTOM_UPLOAD_TOKEN}"
    path = _write_yaml(tmp_path, data)
    cfg = load_config(path, env={"CUSTOM_UPLOAD_TOKEN": "env-token"})
    assert cfg.central.upload_token == "env-token"


def test_env_interpolation_missing_env(tmp_path: Path) -> None:
    data = _base_config()
    data["central"]["upload_token"] = "${env:MISSING_TOKEN}"
    path = _write_yaml(tmp_path, data)
    with pytest.raises(ConfigError) as exc:
        load_config(path, env={})
    assert exc.value.code == "ERR_CFG_013"


def test_env_override_nested(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, _base_config())
    cfg = load_config(
        path,
        env={"RADIVAULT_PACS__MAX_CONCURRENCY": "8"},
    )
    assert cfg.pacs.max_concurrency == 8


def test_config_file_not_found() -> None:
    with pytest.raises(ConfigError) as exc:
        load_config("/nonexistent/gateway.yml")
    assert exc.value.code == "ERR_CFG_000"


def test_unsupported_version(tmp_path: Path) -> None:
    data = _base_config()
    data["version"] = 99
    path = _write_yaml(tmp_path, data)
    with pytest.raises(ConfigError):
        load_config(path)
