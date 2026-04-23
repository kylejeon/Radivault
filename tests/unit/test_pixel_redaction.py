"""Redaction fill strategy tests (dev-spec §4.3, FR-14..FR-17)."""

from __future__ import annotations

import importlib.util

import pytest

from radivault_gateway.deid.pixel.ocr_engine import OcrBox
from radivault_gateway.deid.pixel.redaction import (
    apply_redactions,
    reverify_frame,
)

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy not installed (pixel extras absent)",
)


def _mk_image():
    import numpy as np

    return np.full((64, 64), 200, dtype="uint16")


def test_solid_black_fill_sets_bbox_to_zero():
    """AC-5: default fill leaves bbox pixels == 0."""
    img = _mk_image()
    box = OcrBox(x=10, y=10, w=20, h=8, text="foo", confidence=0.9)
    result = apply_redactions(
        img, [box], confidence_threshold=0.6, fill_strategy="solid_black", padding_px=0
    )
    assert result.redacted_count == 1
    region = img[10:18, 10:30]
    assert int(region.max()) == 0
    assert int(region.min()) == 0


def test_padding_is_applied_symmetrically():
    img = _mk_image()
    box = OcrBox(x=20, y=20, w=4, h=4, text="x", confidence=0.9)
    apply_redactions(
        img, [box], confidence_threshold=0.0, fill_strategy="solid_black", padding_px=3
    )
    # bbox with pad = [17..27] x [17..27]
    assert int(img[17, 17]) == 0
    assert int(img[26, 26]) == 0
    # outside padded region untouched
    assert int(img[5, 5]) == 200


def test_low_confidence_boxes_skipped():
    """FR-14: boxes with conf < threshold are not redacted."""
    img = _mk_image()
    low = OcrBox(x=0, y=0, w=10, h=10, text="x", confidence=0.3)
    high = OcrBox(x=30, y=30, w=10, h=10, text="y", confidence=0.95)
    result = apply_redactions(img, [low, high], confidence_threshold=0.6, padding_px=0)
    assert result.redacted_count == 1
    assert result.skipped_low_confidence == 1
    assert int(img[3, 3]) == 200  # low-conf bbox untouched
    assert int(img[33, 33]) == 0  # high-conf bbox redacted


def test_mean_pixel_fill_uses_frame_mean():
    img = _mk_image()
    box = OcrBox(x=5, y=5, w=5, h=5, text="x", confidence=0.9)
    apply_redactions(img, [box], confidence_threshold=0.0, fill_strategy="mean_pixel", padding_px=0)
    # Mean of the (mostly 200) image ≈ 200; bbox should be near mean.
    assert 150 <= int(img[7, 7]) <= 210


def test_reverify_passes_when_no_residuals():
    """AC-6 pass case: solid_black bbox yields 0 residual detections."""
    img = _mk_image()
    box = OcrBox(x=10, y=10, w=10, h=10, text="foo", confidence=0.9)
    apply_redactions(
        img, [box], confidence_threshold=0.0, fill_strategy="solid_black", padding_px=0
    )

    class _FakeEngine:
        engine_name = "fake"

        def detect_text(self, image, *, languages):
            return []

        def version(self) -> str:
            return "0"

    residuals = reverify_frame(
        img,
        [box],
        confidence_threshold=0.6,
        padding_px=2,
        ocr_engine=_FakeEngine(),
        languages=["eng"],
    )
    assert residuals == []


def test_reverify_detects_residuals_when_engine_finds_text():
    """AC-6 fail case: re-OCR with mocked residual → non-empty list."""
    img = _mk_image()
    box = OcrBox(x=10, y=10, w=10, h=10, text="foo", confidence=0.9)

    class _StubEngine:
        engine_name = "stub"

        def detect_text(self, image, *, languages):
            return [OcrBox(x=0, y=0, w=5, h=5, text="residual", confidence=0.92)]

        def version(self) -> str:
            return "0"

    residuals = reverify_frame(
        img,
        [box],
        confidence_threshold=0.6,
        padding_px=2,
        ocr_engine=_StubEngine(),
        languages=["eng"],
    )
    assert len(residuals) == 1
    assert residuals[0].confidence == pytest.approx(0.92)
