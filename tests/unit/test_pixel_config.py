"""Config schema tests for ``deid.pixel.*`` (dev-spec §6.3, FR-40..FR-44)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from radivault_gateway.config import load_config
from radivault_gateway.deid.pixel.config import (
    DEFAULT_EXCLUSION_PATTERNS,
    PixelDeidConfig,
    PixelOcrConfig,
)


def test_defaults_disabled():
    cfg = PixelDeidConfig()
    assert cfg.enabled is False
    assert cfg.ocr.engine == "tesseract"
    assert cfg.ocr.confidence_threshold == 0.60
    assert cfg.defacing.library == "pydeface"
    assert cfg.defacing.min_removed_ratio == 0.05
    assert cfg.defacing.on_missing == "disable"
    # exclusion patterns default matches dev-spec §6.3.
    assert all(p in cfg.defacing.exclusion_patterns for p in DEFAULT_EXCLUSION_PATTERNS)


def test_invalid_engine_rejected():
    with pytest.raises(ValidationError):
        PixelOcrConfig(engine="tessaract")  # typo → not allowed


def test_empty_languages_rejected():
    with pytest.raises(ValidationError):
        PixelOcrConfig(languages=[])


def test_invalid_regex_rejected():
    from radivault_gateway.deid.pixel.config import PixelDefacingConfig

    with pytest.raises(ValidationError):
        PixelDefacingConfig(exclusion_patterns=["[unclosed"])


def test_min_removed_ratio_out_of_range():
    from radivault_gateway.deid.pixel.config import PixelDefacingConfig

    with pytest.raises(ValidationError):
        PixelDefacingConfig(min_removed_ratio=1.5)


def _gateway_cfg(tmp_path: Path, pixel: dict | None = None) -> Path:
    salt_file = tmp_path / "salt"
    salt_file.write_text("0123456789abcdef" * 2)
    deid: dict = {
        "ruleset_version": "v0.1.0",
        "salt": f"${{file:{salt_file}}}",
        "salt_version": 1,
    }
    if pixel is not None:
        deid["pixel"] = pixel
    data = {
        "version": 1,
        "agent": {
            "gateway_id": "gw",
            "hospital_id": "hosp",
            "org_root_oid": "2.25.140737488355328",
        },
        "pacs": {
            "base_url": "https://pacs.example/dicom-web",
            "auth": {"type": "bearer", "token": "t"},
        },
        "deid": deid,
        "staging": {"root": str(tmp_path / "s"), "retention_hours": 72, "max_disk_pct": 80},
        "state": {"db_path": str(tmp_path / "s.db")},
        "audit": {"path": str(tmp_path / "a.log"), "anchor_interval_seconds": 3600},
        "central": {
            "base_url": "http://127.0.0.1:0",
            "upload_token": "u",
            "allow_insecure": True,
        },
    }
    p = tmp_path / "gw.yml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_load_config_with_pixel_default_off(tmp_path: Path):
    """AC-23: missing ``deid.pixel`` key falls back to the default (disabled)."""
    cfg = load_config(_gateway_cfg(tmp_path))
    assert cfg.deid.pixel.enabled is False


def test_load_config_with_pixel_enabled_block(tmp_path: Path):
    cfg = load_config(
        _gateway_cfg(
            tmp_path,
            pixel={
                "enabled": True,
                "ocr": {
                    "engine": "tesseract",
                    "languages": ["kor", "eng"],
                    "confidence_threshold": 0.70,
                    "modality_allowlist": ["SC", "OT", "US"],
                },
                "defacing": {"library": "pydeface", "modalities": ["MR"]},
            },
        )
    )
    assert cfg.deid.pixel.enabled is True
    assert cfg.deid.pixel.ocr.confidence_threshold == 0.70
    assert cfg.deid.pixel.defacing.modalities == ["MR"]


def test_pixel_example_yaml_parses():
    """AC-D-9: the pilot preset YAML must round-trip through validation."""
    path = Path("configs/gateway.pixel.example.yaml")
    data = yaml.safe_load(path.read_text())
    assert data["deid"]["pixel"]["enabled"] is True


def test_env_override_sets_enabled(tmp_path: Path):
    """AC-25: ``RADIVAULT_DEID__PIXEL__ENABLED=true`` overrides YAML."""
    cfg_path = _gateway_cfg(tmp_path)
    cfg = load_config(
        cfg_path,
        env={"RADIVAULT_DEID__PIXEL__ENABLED": "true"},
    )
    assert cfg.deid.pixel.enabled is True


def test_invalid_engine_exits_64_via_loader(tmp_path: Path):
    """AC-24: invalid engine string triggers ERR_CFG_003."""
    cfg_path = _gateway_cfg(
        tmp_path,
        pixel={"enabled": True, "ocr": {"engine": "invalid"}},
    )
    from radivault_gateway.config import ConfigError

    with pytest.raises(ConfigError) as exc:
        load_config(cfg_path)
    assert exc.value.code.startswith("ERR_CFG_")
