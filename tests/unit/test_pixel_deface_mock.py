"""Defacing engine Protocol + mocked adapters (dev-spec §4.4, FR-21..FR-30)."""

from __future__ import annotations

from pathlib import Path

import pytest

from radivault_gateway.deid.pixel.deface_engine import (
    DefaceResult,
    DefacingEngine,
    MridefacerEngine,
    PydefaceEngine,
    build_deface_engine,
)
from radivault_gateway.deid.pixel.errors import PixelDeidEngineError


class _AvailableFake:
    engine_name = "fake_deface"

    def deface_volume(self, volume_path: Path, out_path: Path) -> DefaceResult:
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=0.3,
            duration_ms=500,
            library=self.engine_name,
        )

    def is_available(self) -> bool:
        return True

    def version(self) -> str:
        return "1.0.0"


def test_protocol_satisfaction():
    fake = _AvailableFake()
    assert isinstance(fake, DefacingEngine)


def test_pydeface_is_available_returns_false_on_host():
    """AC-8 variant: host without pydeface → is_available() == False."""
    eng = PydefaceEngine()
    assert eng.is_available() is False  # macOS dev host has neither pydeface nor FSL


def test_mridefacer_is_available_returns_false_on_host():
    eng = MridefacerEngine()
    assert eng.is_available() is False


def test_mridefacer_raises_when_binary_missing():
    eng = MridefacerEngine()
    with pytest.raises(PixelDeidEngineError) as exc:
        eng.deface_volume(Path("/tmp/x.nii.gz"), Path("/tmp/y.nii.gz"))
    assert exc.value.code == "ERR_PIXEL_DEFACE_LIBRARY_MISSING"


def test_unknown_library_raises():
    with pytest.raises(PixelDeidEngineError) as exc:
        build_deface_engine("not-a-real-engine")
    assert exc.value.code == "ERR_PIXEL_DEFACE_LIBRARY_MISSING"


def test_build_engine_returns_pydeface_or_mridefacer():
    assert isinstance(build_deface_engine("pydeface"), PydefaceEngine)
    assert isinstance(build_deface_engine("mridefacer"), MridefacerEngine)


def test_fake_deface_result_fields():
    r = _AvailableFake().deface_volume(Path("/tmp/in.nii.gz"), Path("/tmp/out.nii.gz"))
    assert r.success is True
    assert r.removed_voxel_ratio == 0.3
    assert r.duration_ms == 500
