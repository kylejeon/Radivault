"""Unit tests for scripts/demo_seed/download_tcia.py.

These exercise the plan-only + license-gate paths so the script can be
reviewed ahead of the actual TCIA wiring (dev-spec §8.2). The network
fetch path raises NotImplementedError and is covered by rehearsal R-1,
not by CI.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "demo_seed"
    / "download_tcia.py"
)


@pytest.fixture(scope="module")
def seed_module():
    spec = importlib.util.spec_from_file_location("demo_seed_download", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_plan_only_emits_valid_json(
    seed_module, capsys, tmp_path, monkeypatch
):
    # Minimal config written to tmp_path.
    yaml = pytest.importorskip("yaml")
    cfg = {
        "cache_dir": str(tmp_path / "cache"),
        "collections": [
            {
                "name": "DEMO-CT",
                "modality": "CT",
                "body_part": "CHEST",
                "target_count": 3,
                "license": "CC-BY",
            }
        ],
    }
    cfg_path = tmp_path / "seed.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    rc = seed_module.main(["--config", str(cfg_path), "--plan-only"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed[0]["collection"] == "DEMO-CT"
    assert parsed[0]["target_count"] == 3
    assert parsed[0]["license"] == "CC-BY"


def test_restricted_collection_skipped_by_default(
    seed_module, tmp_path, caplog
):
    yaml = pytest.importorskip("yaml")
    cfg = {
        "cache_dir": str(tmp_path / "cache"),
        "collections": [
            {
                "name": "LIDC-IDRI",
                "modality": "CT",
                "body_part": "CHEST",
                "target_count": 1,
                "license": "RESTRICTED",
            }
        ],
    }
    cfg_path = tmp_path / "seed.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    with caplog.at_level("WARNING", logger="demo_seed.download"):
        rc = seed_module.main(["--config", str(cfg_path), "--dry-run"])
    assert rc == 0
    assert any("skipping_restricted_collection" in r.message for r in caplog.records)


def test_missing_config_returns_exit_2(seed_module, tmp_path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(SystemExit) as exc:
        seed_module.main(["--config", str(missing)])
    assert exc.value.code == 2


def test_dry_run_writes_plan_marker(seed_module, tmp_path):
    yaml = pytest.importorskip("yaml")
    cfg = {
        "cache_dir": str(tmp_path / "cache"),
        "collections": [
            {
                "name": "DEMO-MG",
                "modality": "MG",
                "body_part": "BREAST",
                "target_count": 2,
                "license": "CC-BY",
            }
        ],
    }
    cfg_path = tmp_path / "seed.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    rc = seed_module.main(["--config", str(cfg_path), "--dry-run"])
    assert rc == 0
    # Each study dir has a _plan.txt and a _done.marker? No — the stub
    # writes only a _plan.txt; we only mark done after successful real
    # fetch. Presence of the _plan.txt proves the iteration shape.
    cache = Path(cfg["cache_dir"])
    plans = list(cache.rglob("_plan.txt"))
    assert len(plans) == 2
