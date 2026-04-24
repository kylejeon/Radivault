"""Shared fixtures for tests/demo_seed/*.

We load the demo-seed scripts as modules via importlib rather than
declaring them as a package — they live under ``scripts/demo_seed/``
which is intentionally not part of the installable wheel.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "demo_seed"


def _load(name: str, filename: str):
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"could not locate {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def download_mod():
    return _load("demo_seed_download", "download_tcia.py")


@pytest.fixture(scope="module")
def orthanc_mod():
    return _load("demo_seed_orthanc", "load_orthanc.py")


@pytest.fixture(scope="module")
def buyer_mod():
    return _load("demo_seed_buyer", "seed_buyer.py")


@pytest.fixture(scope="module")
def hospital_mod():
    return _load("demo_seed_hospital", "seed_hospital.py")


@pytest.fixture(scope="module")
def verify_mod():
    return _load("demo_seed_verify", "verify.py")
