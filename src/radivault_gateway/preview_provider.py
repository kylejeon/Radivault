"""Concrete ``SeriesInputsProvider`` (jpg-preview-defacing FR-PREVIEW-2).

Round 2 closeout of the round-1 punt — round 1 shipped
``_empty_series_inputs`` as the default so ``with_preview_pipeline``
always returned ``series=[]``. Without a real provider, ``process_study``
generated zero JPGs, central persisted nothing, and the search-side
preview-manifest endpoint always 404'd → BFF fell back to the legacy
SliceViewer. This module fills that gap.

Discovery model
---------------
The gateway already stages every ingested study under the layout that
``StagingManager`` defined (FR-14):

    {staging_root}/{pseudo_study_uid}/{pseudo_series_uid}/{pseudo_sop_uid}.dcm

So the provider is "list every series subdir under the study dir, peek
at the first DICOM in each to extract metadata, return one
``SeriesInput`` per series."

The staging root is read from the ``RADIVAULT_STAGING_ROOT`` env var
(consistent with how ``StagingManager`` reads its root from gateway
config). When the path does not exist for a given study (e.g. the
``mock_runner`` smoke path doesn't actually stage DICOMs to disk), we
return ``[]`` — that matches the round-1 ``_empty_series_inputs``
behaviour and is exactly what ``with_preview_pipeline`` expects per
the dev-spec FR-DEFACE-8 invariant ("preview failures never propagate").

Tag extraction
--------------
We need 4 fields from the first DICOM per series (FR-DEFACE-2):

  * Modality
  * BodyPartExamined
  * StudyDescription
  * SeriesDescription / ProtocolName

These are the inputs to ``decide_deface``. We only read one DICOM per
series — the dev-spec FR-DEFACE-2 guarantees these tags are uniform
across the series after De-ID, and reading more would be wasted I/O.

NIfTI conversion
----------------
The dev-spec FR-DEFACE-7 puts ``dcm2niix`` *inside* the sidecar — the
provider hands the sidecar a tar of DICOM files, and conversion happens
there. The provider never builds a NIfTI directly. (``deface_client.py``
already handles the tar packing — see ``_tar_dicom_dir``.)

Defensive degradation
---------------------
* No staging root configured → return ``[]``
* Staging root exists but study dir missing → return ``[]`` (mock path)
* Series dir empty → skip series (don't emit a SeriesInput with no inputs)
* DICOM read fails → log + skip the series
* pydicom missing → return ``[]`` (gateway should always have pydicom
  per pyproject.toml, but defensive)

Anything more aggressive would risk the FR-DEFACE-8 invariant: a
provider exception is caught by ``with_preview_pipeline`` but skipping
gracefully here means the gateway pipeline keeps running.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from radivault_gateway.preview_pipeline import SeriesInput
from radivault_gateway.transfer.claim import Claim

log = logging.getLogger("radivault_gateway.preview_provider")

DEFAULT_STAGING_ROOT = "/var/lib/radivault/staging"


def gateway_series_inputs_provider(
    *, claim: Claim, manifest_entry: dict[str, Any]
) -> list[SeriesInput]:
    """Walk the on-disk staging dir for the study, return one
    :class:`SeriesInput` per series.

    Wired into the CLI by :func:`radivault_gateway.transfer.cli
    ._build_wrapped_runner` when ``PREVIEW_PIPELINE_ENABLED=true``.
    """
    pseudo_study_uid = manifest_entry.get("pseudo_study_uid")
    if not pseudo_study_uid:
        return []

    staging_root_str = os.environ.get(
        "RADIVAULT_STAGING_ROOT", DEFAULT_STAGING_ROOT
    )
    staging_root = Path(staging_root_str)
    study_dir = staging_root / pseudo_study_uid
    return _collect_series_inputs(study_dir=study_dir)


def _collect_series_inputs(*, study_dir: Path) -> list[SeriesInput]:
    """Pure helper — given a staged study dir, build SeriesInputs.

    Split out from the env-var-aware top-level so unit tests can drive
    the directory layout directly via ``tmp_path`` without monkey-
    patching the environment.
    """
    if not study_dir.exists() or not study_dir.is_dir():
        log.debug(
            "preview_provider_study_dir_missing",
            extra={
                "event": "preview.provider.miss",
                "study_dir": str(study_dir),
            },
        )
        return []

    try:
        import pydicom  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - gateway always has pydicom
        log.warning(
            "preview_provider_pydicom_missing",
            extra={"event": "preview.provider.error"},
        )
        return []

    out: list[SeriesInput] = []
    series_num = 0
    for series_dir in sorted(study_dir.iterdir()):
        if not series_dir.is_dir():
            continue
        # Find the first readable DICOM file in this series.
        first = _first_dicom(series_dir)
        if first is None:
            log.debug(
                "preview_provider_empty_series",
                extra={
                    "event": "preview.provider.skip",
                    "series_dir": str(series_dir),
                },
            )
            continue
        try:
            ds = pydicom.dcmread(first, stop_before_pixels=True, force=False)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "preview_provider_dcmread_failed",
                extra={
                    "event": "preview.provider.error",
                    "path": str(first),
                    "error": str(exc)[:200],
                },
            )
            continue
        series_num += 1
        out.append(
            SeriesInput(
                pseudo_series_uid=series_dir.name,
                series_num=series_num,
                series_dir=series_dir,
                modality=_str_or_none(getattr(ds, "Modality", None)),
                body_part=_str_or_none(getattr(ds, "BodyPartExamined", None)),
                series_description=_str_or_none(
                    getattr(ds, "SeriesDescription", None)
                ),
                protocol_name=_str_or_none(
                    getattr(ds, "ProtocolName", None)
                ),
            )
        )
    log.info(
        "preview_provider_built",
        extra={
            "event": "preview.provider.ok",
            "study_dir": str(study_dir),
            "n_series": len(out),
        },
    )
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_dicom(series_dir: Path) -> Path | None:
    """Return the first regular file under ``series_dir`` (sorted).

    We don't filter by extension — staging emits files with the
    ``.dcm`` suffix, but a DICOM tarball etc. could also live here.
    The next-step ``pydicom.dcmread`` is the actual content gate.
    """
    for path in sorted(series_dir.rglob("*")):
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _str_or_none(value: Any) -> str | None:
    """Coerce a pydicom value (which may be MultiValue / DA / DS / None)
    to a stripped string, or None if empty/whitespace.
    """
    if value is None:
        return None
    s = str(value).strip()
    return s or None


__all__ = [
    "DEFAULT_STAGING_ROOT",
    "gateway_series_inputs_provider",
]
