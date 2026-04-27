"""Unit tests for ``_resolve_afni_output`` in ``docker/afni-refacer/app.py``.

Covers the MAJOR-1 silent-corruption guard added to the AFNI sidecar:

* The exact-match probes (`.deface.nii.gz`, `.nii.gz`) win regardless of
  whether the caller passed the ``-prefix`` with or without a trailing
  ``.nii.gz`` suffix (the gateway now passes *with*, but we keep the
  resolver tolerant of both shapes).
* The directory-glob fallback explicitly excludes AFNI's known
  side-outputs — ``*.face.nii.gz`` (the face mask, i.e. the *region to
  be zeroed*), ``*.skullstrip.nii.gz``, and ``*.mask.nii.gz`` — so a
  regression in the prefix convention can never let a non-defaced
  NIfTI leak out as the defaced output.

The sidecar isn't a Python package, so we load ``app.py`` by file path
and only exercise the pure ``_resolve_afni_output`` helper.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = REPO_ROOT / "docker" / "afni-refacer" / "app.py"


def _load_sidecar_module():
    spec = importlib.util.spec_from_file_location(
        "afni_refacer_sidecar_app", str(APP_PATH)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sidecar():
    return _load_sidecar_module()


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x1f\x8b\x08\x00")  # gzip magic; resolver only checks existence
    return path


# ---------------------------------------------------------------------------
# Exact-match probes (the new prefix convention is `<dir>/defaced.nii.gz`).
# ---------------------------------------------------------------------------


def test_resolves_deface_nii_gz_when_present(tmp_path: Path, sidecar) -> None:
    prefix = tmp_path / "defaced.nii.gz"  # MAJOR-1 fix prefix shape
    expected = _touch(tmp_path / "defaced.deface.nii.gz")

    got = sidecar._resolve_afni_output(prefix)

    assert got == expected


def test_resolves_plain_nii_gz_when_only_that_exists(tmp_path: Path, sidecar) -> None:
    prefix = tmp_path / "defaced.nii.gz"
    expected = _touch(tmp_path / "defaced.nii.gz")

    got = sidecar._resolve_afni_output(prefix)

    assert got == expected


def test_deface_nii_gz_wins_over_plain_nii_gz(tmp_path: Path, sidecar) -> None:
    """When both the canonical defaced output and the plain prefix file
    exist, search order #1 (`.deface.nii.gz`) must be returned — that
    is the AFNI mode_deface canonical filename.
    """
    prefix = tmp_path / "defaced.nii.gz"
    deface = _touch(tmp_path / "defaced.deface.nii.gz")
    _touch(tmp_path / "defaced.nii.gz")

    got = sidecar._resolve_afni_output(prefix)

    assert got == deface


def test_resolves_with_legacy_no_suffix_prefix(tmp_path: Path, sidecar) -> None:
    """Backwards-compat: a prefix without `.nii.gz` (legacy callers)
    still resolves correctly via the same probe order.
    """
    prefix = tmp_path / "defaced"
    expected = _touch(tmp_path / "defaced.deface.nii.gz")

    got = sidecar._resolve_afni_output(prefix)

    assert got == expected


# ---------------------------------------------------------------------------
# Fallback safety — silent-corruption guard.
# ---------------------------------------------------------------------------


def test_returns_none_when_only_face_mask_present(tmp_path: Path, sidecar) -> None:
    """If AFNI emitted only the *face mask* (the region to be zeroed)
    and nothing else, the resolver MUST return None instead of letting
    the glob fallback hand the face mask to the caller.
    """
    prefix = tmp_path / "defaced.nii.gz"
    _touch(tmp_path / "defaced.face.nii.gz")  # face mask only — must NOT match

    got = sidecar._resolve_afni_output(prefix)

    assert got is None


def test_excludes_skullstrip_and_mask_in_fallback(tmp_path: Path, sidecar) -> None:
    """`*.skullstrip.nii.gz` and `*.mask.nii.gz` are also AFNI auxiliary
    volumes; the fallback must skip them.
    """
    prefix = tmp_path / "defaced.nii.gz"
    _touch(tmp_path / "defaced.face.nii.gz")
    _touch(tmp_path / "defaced.skullstrip.nii.gz")
    _touch(tmp_path / "defaced.mask.nii.gz")

    got = sidecar._resolve_afni_output(prefix)

    assert got is None


def test_fallback_picks_unrelated_nii_gz_when_exact_misses(
    tmp_path: Path, sidecar
) -> None:
    """If exact-match probes miss but a benign `.nii.gz` is present,
    the fallback still works (preserving the original resolver
    contract). This guards against regressions where the fallback
    becomes too aggressive and blocks legitimate inputs.
    """
    prefix = tmp_path / "different_name.nii.gz"
    expected = _touch(tmp_path / "weirdly_named_deface.nii.gz")

    got = sidecar._resolve_afni_output(prefix)

    assert got == expected


def test_returns_none_when_directory_empty(tmp_path: Path, sidecar) -> None:
    prefix = tmp_path / "defaced.nii.gz"

    got = sidecar._resolve_afni_output(prefix)

    assert got is None
