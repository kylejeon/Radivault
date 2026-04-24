"""DICOM JSON (PS3.18 §F) → pydicom Dataset conversion helpers.

Used by Flow A (metadata-only sync) to turn WADO-RS ``/studies/{uid}/metadata``
responses into on-disk Part-10 DICOM files that the existing de-ID engine can
consume without modification. Pixel data is intentionally dropped — every
``BulkDataURI`` reference in the JSON is resolved to ``None`` so the resulting
Dataset carries metadata only.

The round-trip (JSON → Dataset → ``save_as`` → ``dcmread``) is required because
:class:`radivault_gateway.deid.DeidEngine` reads its input from a filesystem
directory (FR-6..FR-13 operate on Part-10 files). Synthesising a Part-10 file
keeps the de-ID path bit-equivalent between Flow A and Flow B.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

log = logging.getLogger("radivault.pacs.dicom_json")


# PS3.10 preamble — 128 NUL bytes (the ``DICM`` prefix is emitted by
# ``save_as`` when ``enforce_file_format=True``).
_PREAMBLE = b"\0" * 128

# Fallback SOPClassUID used when the JSON payload omits it (rare but seen with
# older DICOMweb servers). Secondary Capture is chosen because it has no
# pixel-layout preconditions that could confuse the de-ID engine.
_FALLBACK_SOP_CLASS = "1.2.840.10008.5.1.4.1.1.7"


def _drop_bulk_data(*_args: Any, **_kwargs: Any) -> None:
    """BulkDataURI handler that returns ``None`` for every reference.

    WADO-RS metadata responses encode ``PixelData`` (and other large VRs) as
    ``BulkDataURI`` pointers rather than inline bytes. We deliberately discard
    these references — Flow A never transfers pixels to Central, so resolving
    them would defeat the bandwidth win.
    """
    return None


def json_to_dataset(instance_json: dict[str, Any]) -> Dataset:
    """Convert a single DICOM JSON instance dict into a pydicom Dataset.

    The returned Dataset has group-0002 elements split into ``file_meta`` so
    that a subsequent ``ds.save_as(path, enforce_file_format=True)`` writes a
    valid Part-10 file. Missing mandatory file-meta elements
    (``TransferSyntaxUID``, ``MediaStorageSOPClassUID``,
    ``MediaStorageSOPInstanceUID``) are backfilled with conservative defaults.
    """
    ds = Dataset.from_json(instance_json, bulk_data_uri_handler=_drop_bulk_data)

    # PS3.18 metadata responses may emit group-0002 (file-meta) elements
    # alongside the rest of the dataset. pydicom requires them to live on
    # ``ds.file_meta`` as a FileMetaDataset. BulkDataURI-only elements (most
    # notably ``PixelData``) retain a ``None`` value after ``from_json`` —
    # drop them so downstream consumers see an honest metadata-only payload.
    fm = FileMetaDataset()
    for tag in list(ds.keys()):
        if tag.group == 0x0002:
            fm[tag] = ds[tag]
            del ds[tag]
            continue
        elem = ds[tag]
        if elem.value is None:
            del ds[tag]

    if not getattr(fm, "TransferSyntaxUID", None):
        fm.TransferSyntaxUID = ExplicitVRLittleEndian
    if not getattr(fm, "MediaStorageSOPInstanceUID", None):
        sop = ds.get("SOPInstanceUID")
        if sop:
            fm.MediaStorageSOPInstanceUID = sop
    if not getattr(fm, "MediaStorageSOPClassUID", None):
        sop_class = ds.get("SOPClassUID")
        fm.MediaStorageSOPClassUID = sop_class or _FALLBACK_SOP_CLASS

    ds.file_meta = fm
    ds.preamble = _PREAMBLE
    # ``is_little_endian`` / ``is_implicit_VR`` are deprecated in pydicom 3.x
    # and removed in 4.0. ``TransferSyntaxUID`` on ``file_meta`` is the
    # authoritative source for ``save_as(..., enforce_file_format=True)``, so
    # we deliberately omit them here to keep the gateway logs clean when a
    # sync-once materialises hundreds of instances.
    return ds


def json_to_datasets(study_json: list[dict[str, Any]]) -> list[Dataset]:
    """Convert a study-level DICOM JSON array into a list of Datasets.

    Instances that cannot be parsed are skipped and logged at WARNING; the
    caller sees only the datasets that round-tripped cleanly. An empty input
    list yields an empty output list (the caller decides whether that is an
    error).
    """
    datasets: list[Dataset] = []
    for idx, item in enumerate(study_json):
        try:
            datasets.append(json_to_dataset(item))
        except Exception as exc:
            log.warning(
                "dicom_json.skip",
                extra={"index": idx, "error": str(exc)[:200]},
            )
    return datasets


def write_datasets_to_dir(datasets: list[Dataset], out_dir: Path) -> tuple[list[Path], int]:
    """Serialise Datasets to Part-10 ``.dcm`` files under ``out_dir``.

    Returns ``(paths, total_bytes)`` so callers can reuse the tuple shape of
    :class:`radivault_gateway.pacs.FetchResult`. Filenames use a zero-padded
    index to preserve a stable sort order — the same convention the
    multipart WADO-RS path uses.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    total_bytes = 0
    for idx, ds in enumerate(datasets):
        path = out_dir / f"{idx:05d}.dcm"
        # enforce_file_format=True writes preamble + DICM prefix + file_meta
        # in Part-10 format; pydicom.dcmread(path) then round-trips cleanly.
        ds.save_as(path, enforce_file_format=True)
        paths.append(path)
        total_bytes += path.stat().st_size
    return paths, total_bytes
