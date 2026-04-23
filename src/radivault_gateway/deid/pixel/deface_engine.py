"""Defacing engine Protocol + pydeface / mridefacer adapters (dev-spec §4.4).

Both implementations guard heavy imports (``pydeface``, ``nibabel``) and
external binary calls (``mridefacer``) so the module imports cleanly on hosts
that lack the pixel extras. The orchestrator chooses between engines via the
``deid.pixel.defacing.library`` config and falls back to mridefacer when
``deid.pixel.defacing.fallback=true`` (default).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from radivault_gateway.deid.pixel.errors import PixelDeidEngineError

log = logging.getLogger("radivault.pipeline")


@dataclass(frozen=True)
class DefaceResult:
    success: bool
    out_volume_path: Path
    removed_voxel_ratio: float  # 0..1
    duration_ms: int
    library: str = ""


@runtime_checkable
class DefacingEngine(Protocol):
    engine_name: str

    def deface_volume(self, volume_path: Path, out_path: Path) -> DefaceResult: ...

    def is_available(self) -> bool: ...

    def version(self) -> str: ...


class PydefaceEngine:
    """pydeface + FSL flirt.

    pydeface requires NIfTI input. The orchestrator is responsible for
    DICOM↔NIfTI conversion; this engine only consumes/produces NIfTI volumes.
    """

    engine_name: str = "pydeface"

    def __init__(self) -> None:
        self._version_cache: str | None = None

    def is_available(self) -> bool:
        try:
            import nibabel  # type: ignore[import-not-found]  # noqa: F401
            import pydeface  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return False
        # FSL's ``flirt`` is required by pydeface at runtime.
        return shutil.which("flirt") is not None

    def version(self) -> str:
        if self._version_cache:
            return self._version_cache
        try:
            import pydeface  # type: ignore[import-not-found]

            self._version_cache = getattr(pydeface, "__version__", "unknown")
        except Exception:
            self._version_cache = "unknown"
        return self._version_cache

    def deface_volume(self, volume_path: Path, out_path: Path) -> DefaceResult:
        import time

        try:
            import nibabel as nib  # type: ignore[import-not-found]
            import numpy as np  # type: ignore[import-not-found]
            from pydeface.utils import deface_image  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PixelDeidEngineError(
                "ERR_PIXEL_DEFACE_LIBRARY_MISSING",
                f"pydeface/nibabel missing: {exc}",
            ) from exc
        started = time.monotonic()
        try:
            # pydeface.deface_image writes to out_path when given outfile kwarg.
            deface_image(  # pragma: no cover - live only
                infile=str(volume_path), outfile=str(out_path), force=True
            )
        except Exception as exc:
            raise PixelDeidEngineError(
                "ERR_PIXEL_DEFACE_FAILURE",
                f"pydeface failed: {exc}",
            ) from exc
        duration_ms = int((time.monotonic() - started) * 1000)
        # Estimate removed-voxel ratio: difference in nonzero count over the
        # approximate face bounding box (front 1/3 of slices). For v0.2 this is
        # a conservative heuristic; the QA spec tracks it in Prom metrics.
        try:
            before = nib.load(str(volume_path)).get_fdata()  # pragma: no cover - live only
            after = nib.load(str(out_path)).get_fdata()  # pragma: no cover - live only
            ratio = _estimate_removed_ratio(before, after, np)  # pragma: no cover - live only
        except Exception:
            ratio = 0.0
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=float(ratio),
            duration_ms=duration_ms,
            library=self.engine_name,
        )


class MridefacerEngine:
    """mridefacer CLI (BSD-3).

    Invoked via subprocess. Fallback for PydefaceEngine failures when
    ``deid.pixel.defacing.fallback=true``.
    """

    engine_name: str = "mridefacer"

    def __init__(self) -> None:
        self._version_cache: str | None = None

    def is_available(self) -> bool:
        return shutil.which("mridefacer") is not None

    def version(self) -> str:
        if self._version_cache:
            return self._version_cache
        if not self.is_available():
            self._version_cache = "absent"
            return self._version_cache
        try:
            out = subprocess.run(  # pragma: no cover - live only
                ["mridefacer", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._version_cache = (out.stdout or out.stderr).strip() or "unknown"
        except Exception:
            self._version_cache = "unknown"
        return self._version_cache

    def deface_volume(self, volume_path: Path, out_path: Path) -> DefaceResult:
        import time

        if not self.is_available():
            raise PixelDeidEngineError(
                "ERR_PIXEL_DEFACE_LIBRARY_MISSING",
                "mridefacer binary not on PATH",
            )
        started = time.monotonic()
        try:
            subprocess.run(  # pragma: no cover - live only
                ["mridefacer", str(volume_path), str(out_path)],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - live only
            raise PixelDeidEngineError(
                "ERR_PIXEL_DEFACE_FAILURE",
                f"mridefacer failed: {exc.stderr!r}",
            ) from exc
        duration_ms = int((time.monotonic() - started) * 1000)
        return DefaceResult(
            success=True,
            out_volume_path=out_path,
            removed_voxel_ratio=0.0,
            duration_ms=duration_ms,
            library=self.engine_name,
        )


def _estimate_removed_ratio(before, after, np_mod) -> float:  # pragma: no cover - live only
    """Rough removed-voxel ratio over the anterior third of the volume.

    We approximate the face bounding-box as the anterior 1/3 along the Y axis
    and compute ``(nonzero_before - nonzero_after) / nonzero_before``.
    """
    if before.shape != after.shape or before.ndim < 2:
        return 0.0
    y_len = before.shape[1]
    y_end = max(1, y_len // 3)
    before_slab = before[:, :y_end]
    after_slab = after[:, :y_end]
    nz_before = np_mod.count_nonzero(before_slab)
    if nz_before == 0:
        return 0.0
    nz_after = np_mod.count_nonzero(after_slab)
    return float(max(0.0, (nz_before - nz_after) / nz_before))


def build_deface_engine(library: str) -> DefacingEngine:
    if library == "pydeface":
        return PydefaceEngine()
    if library == "mridefacer":
        return MridefacerEngine()
    raise PixelDeidEngineError(
        "ERR_PIXEL_DEFACE_LIBRARY_MISSING",
        f"unknown defacing library {library!r}",
    )
