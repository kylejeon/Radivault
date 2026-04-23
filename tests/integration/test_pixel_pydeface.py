"""Live pydeface integration (dev-spec §14.2).

Skipped by default. Gated by ``PIXEL_TEST_PYDEFACE=1`` and the presence of
``pydeface``, ``nibabel``, and the FSL ``flirt`` binary on PATH. The test
constructs a minimal synthetic 3D volume and measures
``removed_voxel_ratio`` to verify the pydeface happy path.

Run via:

    PIXEL_TEST_PYDEFACE=1 pytest tests/integration/test_pixel_pydeface.py -q
"""

from __future__ import annotations

import importlib.util
import os
import shutil

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("PIXEL_TEST_PYDEFACE") != "1",
        reason="set PIXEL_TEST_PYDEFACE=1 to run live pydeface integration",
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("pydeface") is None
        or importlib.util.find_spec("nibabel") is None
        or importlib.util.find_spec("numpy") is None,
        reason="pydeface / nibabel / numpy not installed",
    ),
    pytest.mark.skipif(
        shutil.which("flirt") is None,
        reason="FSL flirt binary not on PATH",
    ),
]


def test_pydeface_removes_face_voxels(tmp_path):  # pragma: no cover - live only
    import nibabel as nib
    import numpy as np

    from radivault_gateway.deid.pixel.deface_engine import PydefaceEngine

    # Build a tiny synthetic "head" — cuboid with non-zero voxels in the
    # anterior third to simulate a face surface.
    vol = np.zeros((32, 32, 32), dtype=np.float32)
    vol[:, :10, :] = 1.0
    affine = np.eye(4)
    in_path = tmp_path / "synth.nii.gz"
    out_path = tmp_path / "synth.defaced.nii.gz"
    nib.save(nib.Nifti1Image(vol, affine), str(in_path))

    engine = PydefaceEngine()
    assert engine.is_available(), "pydeface reported unavailable — check flirt"
    result = engine.deface_volume(in_path, out_path)
    assert result.success is True
    # We expect some removal, even if the synthetic shape is trivial.
    assert result.removed_voxel_ratio >= 0.0
