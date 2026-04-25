"""Ingest-time DICOM thumbnail generator (dev-spec FR-THUMB-1).

Produces a 256x256 JPEG of the **middle slice** of the largest series for a
study, for buyer-portal preview cards. PHI is gated by:

1. ``BurnedInAnnotation == "YES"`` (0028,0301) → skip (returns ``None``).
2. Modality whitelist (CT/MR/CR/DR/DX) → unknown modalities are also skipped
   (``phi_scrub_status="skipped_unknown"``) for conservative MVP behaviour.

VOI LUT / windowing precedence:
- Apply ``apply_modality_lut`` + ``apply_voi_lut`` from pydicom when possible.
- Fallback per modality:
  * CT: WindowCenter/Width DICOM tags → BodyPart-based defaults
    (CHEST 1500/-600, ABDOMEN 400/50, HEAD 80/40, default 400/40).
  * MR: percentile p1-p99 normalize.
  * CR/DR/DX/MG: percentile p1-p99 normalize.
  * US: passthrough (already 8-bit).

JPEG payload is quality 85, EXIF-stripped, no ICC profile.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

log = logging.getLogger("radivault.thumbnail")

THUMBNAIL_SIZE = (256, 256)
JPEG_QUALITY = 85
SAFE_MODALITIES = {"CT", "MR", "CR", "DR", "DX", "MG"}


@dataclass
class ThumbnailResult:
    bytes: bytes
    sha256: str
    source_instance_uid_pseudo: str
    slice_index: int
    slice_count: int
    width: int = 256
    height: int = 256
    format: str = "JPEG"
    phi_scrub_status: str = "passed"
    phi_scrub_method: str = "burned_in_tag_gate"


def _ct_window_for_body_part(body_part: str | None) -> tuple[float, float]:
    """Return (center, width) HU defaults for CT modality."""
    bp = (body_part or "").upper()
    if "HEAD" in bp or "BRAIN" in bp:
        return (40.0, 80.0)
    if "CHEST" in bp or "LUNG" in bp or "THORAX" in bp:
        return (-600.0, 1500.0)
    if "ABDOMEN" in bp or "PELVIS" in bp or "ABD" in bp:
        return (50.0, 400.0)
    return (40.0, 400.0)


def _array_to_uint8(arr, ds, modality: str, body_part: str | None):
    """Window 16-bit pixel array → uint8 grayscale numpy array."""
    import numpy as np

    arr = arr.astype("float32", copy=False)

    # Try DICOM-native VOI LUT first (works for CR/DR/DX commonly).
    try:
        from pydicom.pixel_data_handlers.util import apply_modality_lut, apply_voi_lut

        try:
            arr = apply_modality_lut(arr, ds)
        except Exception:
            pass
        if hasattr(ds, "WindowCenter") or hasattr(ds, "VOILUTSequence"):
            try:
                arr = apply_voi_lut(arr, ds)
                # apply_voi_lut may return uint8 directly; clip + return.
                if arr.dtype != np.float32:
                    arr = arr.astype("float32", copy=False)
                lo, hi = float(arr.min()), float(arr.max())
                if hi > lo:
                    arr = (arr - lo) / (hi - lo) * 255.0
                else:
                    arr = arr * 0
                return np.clip(arr, 0, 255).astype("uint8")
            except Exception:
                pass
    except ImportError:
        pass

    # Fallback windowing per modality.
    if modality == "CT":
        # Prefer DICOM tag (some studies are pre-windowed).
        center = getattr(ds, "WindowCenter", None)
        width = getattr(ds, "WindowWidth", None)
        if center is None or width is None:
            center, width = _ct_window_for_body_part(body_part)
        else:
            # Multivalue → first.
            try:
                center = float(center[0] if hasattr(center, "__iter__") else center)
                width = float(width[0] if hasattr(width, "__iter__") else width)
            except (TypeError, ValueError):
                center, width = _ct_window_for_body_part(body_part)
        lo = center - width / 2
        hi = center + width / 2
    elif modality in ("MR", "CR", "DR", "DX", "MG"):
        lo = float(np.percentile(arr, 1))
        hi = float(np.percentile(arr, 99))
    else:
        # passthrough (US already 8-bit display-ready); just clip to its own range.
        lo = float(arr.min())
        hi = float(arr.max())

    if hi <= lo:
        return np.zeros(arr.shape, dtype="uint8")
    arr = (arr - lo) / (hi - lo) * 255.0
    return np.clip(arr, 0, 255).astype("uint8")


def generate_thumbnail(
    instances: list[Path],
    *,
    modality: str | None = None,
    body_part: str | None = None,
) -> ThumbnailResult | None:
    """Pick the middle slice and render a 256x256 JPEG.

    Returns ``None`` when generation is skipped for PHI safety:
    - BurnedInAnnotation == "YES"
    - modality not in {CT, MR, CR, DR, DX, MG}
    - any pydicom / image error

    Returns a populated :class:`ThumbnailResult` otherwise. ``phi_scrub_status``
    is set to ``"skipped_burned_in"`` / ``"skipped_unknown"`` / ``"passed"``
    accordingly — when ``None`` is returned, the caller should record the skip
    reason via the ``phi_scrub_status`` it assumes for null results
    (``"skipped_burned_in"`` for Yes, ``"skipped_unknown"`` for non-whitelist).
    """
    if not instances:
        return None
    try:
        import pydicom
    except ImportError:
        log.warning("pydicom_unavailable", extra={"event": "thumbnail.dep_missing"})
        return None
    try:
        import numpy as np  # noqa: F401
    except ImportError:
        log.warning("numpy_unavailable", extra={"event": "thumbnail.dep_missing"})
        return None
    try:
        from PIL import Image
    except ImportError:
        log.warning("pillow_unavailable", extra={"event": "thumbnail.dep_missing"})
        return None

    # Sort by InstanceNumber ASC, fallback SOPInstanceUID lexical.
    parsed: list[tuple[int | None, str, Path, pydicom.Dataset]] = []
    for path in instances:
        try:
            ds = pydicom.dcmread(path, force=False)
        except Exception:
            continue
        # Burn-in gate (FR-THUMB-1 PHI scrub).
        burned = str(getattr(ds, "BurnedInAnnotation", "") or "").upper().strip()
        if burned == "YES":
            log.info(
                "thumbnail_skip_burned_in",
                extra={"event": "thumbnail.skip", "reason": "burned_in_yes"},
            )
            return None
        in_no = getattr(ds, "InstanceNumber", None)
        try:
            in_no_int: int | None = int(in_no) if in_no is not None else None
        except (TypeError, ValueError):
            in_no_int = None
        sop_uid = str(getattr(ds, "SOPInstanceUID", "") or "")
        parsed.append((in_no_int, sop_uid, path, ds))

    if not parsed:
        return None

    # Modality whitelist gate.
    eff_modality = (modality or "").upper()
    if not eff_modality:
        eff_modality = str(getattr(parsed[0][3], "Modality", "") or "").upper()
    if eff_modality not in SAFE_MODALITIES:
        log.info(
            "thumbnail_skip_unknown_modality",
            extra={
                "event": "thumbnail.skip",
                "reason": "modality_not_whitelisted",
                "modality": eff_modality,
            },
        )
        return None

    parsed.sort(key=lambda p: (p[0] if p[0] is not None else 1 << 30, p[1]))
    middle = len(parsed) // 2
    _, sop_uid, _path, ds = parsed[middle]

    try:
        arr = ds.pixel_array
    except Exception as exc:
        log.warning(
            "thumbnail_pixel_array_fail",
            extra={"event": "thumbnail.error", "error": str(exc)[:200]},
        )
        return None

    # multi-frame handling — pick middle frame.
    if arr.ndim == 3:
        n_frames = int(getattr(ds, "NumberOfFrames", arr.shape[0]) or arr.shape[0])
        frame_idx = max(0, min(n_frames // 2, arr.shape[0] - 1))
        arr = arr[frame_idx]

    if arr.ndim > 2:
        # RGB / palette → reduce to luminance for thumbnail.
        try:
            import numpy as np

            arr = np.mean(arr, axis=-1)
        except Exception:
            return None

    try:
        u8 = _array_to_uint8(arr, ds, eff_modality, body_part)
    except Exception as exc:
        log.warning(
            "thumbnail_window_fail",
            extra={"event": "thumbnail.error", "error": str(exc)[:200]},
        )
        return None

    try:
        img = Image.fromarray(u8, mode="L")
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        jpeg_bytes = buf.getvalue()
    except Exception as exc:
        log.warning(
            "thumbnail_encode_fail",
            extra={"event": "thumbnail.error", "error": str(exc)[:200]},
        )
        return None

    return ThumbnailResult(
        bytes=jpeg_bytes,
        sha256=hashlib.sha256(jpeg_bytes).hexdigest(),
        source_instance_uid_pseudo=sop_uid,
        slice_index=middle,
        slice_count=len(parsed),
        width=img.width,
        height=img.height,
        format="JPEG",
        phi_scrub_status="passed",
        phi_scrub_method="burned_in_tag_gate",
    )
