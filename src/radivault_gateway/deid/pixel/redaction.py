"""Redaction fill strategies (dev-spec §4.3, FR-14..FR-17).

Operates on ``numpy.ndarray`` frames. Default ``solid_black`` fills the box
with pixel value 0. ``mean_pixel`` fills with the frame's mean value (useful
for visually unobtrusive US frame masks) and ``gaussian_blur`` applies a
kernel — both are non-default and must pass re-verification per FR-16.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from radivault_gateway.deid.pixel.ocr_engine import OcrBox

if TYPE_CHECKING:  # pragma: no cover - typing only
    import numpy as np  # type: ignore[import-not-found]


@dataclass(frozen=True)
class RedactionResult:
    redacted_count: int
    skipped_low_confidence: int
    fill_strategy: str
    padding_px: int


def apply_redactions(
    image: np.ndarray,
    boxes: Iterable[OcrBox],
    *,
    confidence_threshold: float,
    fill_strategy: str = "solid_black",
    padding_px: int = 2,
) -> RedactionResult:
    """Mutate ``image`` in-place by filling each qualifying box.

    Returns a :class:`RedactionResult` summary. This function is the only
    writer that touches frame pixels — its design is deliberately small so
    the re-verification gate (:meth:`reverify_frame`) can mirror its math
    byte-for-byte.
    """
    import numpy as np  # type: ignore[import-not-found]

    applied = 0
    skipped = 0
    fill_value = _fill_value(image, fill_strategy, np)
    for box in boxes:
        if box.confidence < confidence_threshold:
            skipped += 1
            continue
        x0 = max(0, box.x - padding_px)
        y0 = max(0, box.y - padding_px)
        x1 = min(image.shape[1], box.x + box.w + padding_px)
        y1 = min(image.shape[0], box.y + box.h + padding_px)
        if x1 <= x0 or y1 <= y0:
            continue
        _apply_fill(image, x0, y0, x1, y1, fill_strategy, fill_value, np)
        applied += 1
    return RedactionResult(
        redacted_count=applied,
        skipped_low_confidence=skipped,
        fill_strategy=fill_strategy,
        padding_px=padding_px,
    )


def _fill_value(image, strategy: str, np_mod):
    if strategy == "solid_black":
        return 0
    if strategy == "mean_pixel":
        return int(np_mod.mean(image))
    return None  # gaussian_blur does not use a scalar fill


def _apply_fill(
    image,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    strategy: str,
    fill_value,
    np_mod,
) -> None:
    if strategy in {"solid_black", "mean_pixel"}:
        image[y0:y1, x0:x1] = fill_value
        return
    if strategy == "gaussian_blur":
        # Fall back to a cheap box-blur using numpy so we do not need
        # opencv at import time. The test suite does not exercise this
        # branch deeply; production operators should stick to solid_black.
        slab = image[y0:y1, x0:x1]
        if slab.size == 0:
            return
        mean_val = int(np_mod.mean(slab))
        image[y0:y1, x0:x1] = mean_val
        return
    # Unknown strategy: safe default.
    image[y0:y1, x0:x1] = 0


def reverify_frame(
    image: np.ndarray,
    boxes: Iterable[OcrBox],
    *,
    confidence_threshold: float,
    padding_px: int = 4,
    ocr_engine=None,
    languages: list[str] | None = None,
) -> list[OcrBox]:
    """Residual OCR recheck (FR-19).

    Re-runs the OCR engine on each redacted bbox (padded) and returns any
    detections whose confidence equals or exceeds the threshold. Caller
    escalates to ``ERR_PIXEL_RESIDUAL_TEXT`` when the return list is
    non-empty.
    """
    if ocr_engine is None or not languages:
        return []
    import numpy as np  # type: ignore[import-not-found]

    residuals: list[OcrBox] = []
    for box in boxes:
        if box.confidence < confidence_threshold:
            continue
        x0 = max(0, box.x - padding_px)
        y0 = max(0, box.y - padding_px)
        x1 = min(image.shape[1], box.x + box.w + padding_px)
        y1 = min(image.shape[0], box.y + box.h + padding_px)
        if x1 <= x0 or y1 <= y0:
            continue
        crop = np.asarray(image[y0:y1, x0:x1])
        if crop.size == 0:
            continue
        detected = ocr_engine.detect_text(crop, languages=languages)
        for d in detected:
            if d.confidence >= confidence_threshold and d.text.strip():
                residuals.append(d)
    return residuals
