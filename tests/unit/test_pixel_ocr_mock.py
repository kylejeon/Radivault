"""OCR engine Protocol + Tesseract adapter tests (dev-spec §4.2, FR-7..FR-13)."""

from __future__ import annotations

import pytest

from radivault_gateway.deid.pixel.errors import PixelDeidEngineError
from radivault_gateway.deid.pixel.ocr_engine import (
    OcrBox,
    OcrEngine,
    TesseractOcrEngine,
    _boxes_from_tesseract_dict,
    build_ocr_engine,
)


def test_protocol_runtime_check_with_fake_engine():
    class _Fake:
        engine_name = "fake"

        def detect_text(self, image, *, languages):
            return []

        def version(self) -> str:
            return "0"

    assert isinstance(_Fake(), OcrEngine)


def test_boxes_from_tesseract_dict_filters_negative_conf():
    data = {
        "text": ["hello", "", "world"],
        "left": [1, 2, 3],
        "top": [1, 2, 3],
        "width": [10, 10, 10],
        "height": [10, 10, 10],
        "conf": [92, -1, 0.55],
    }
    boxes = _boxes_from_tesseract_dict(data)
    assert len(boxes) == 2
    # 92 → 0.92 normalised, 0.55 → already 0..1
    assert boxes[0].confidence == pytest.approx(0.92)
    assert boxes[1].confidence == pytest.approx(0.55)
    assert all(isinstance(b, OcrBox) for b in boxes)


def test_boxes_from_tesseract_dict_drops_empty_text():
    data = {
        "text": ["", "  ", None],
        "left": [1, 2, 3],
        "top": [1, 2, 3],
        "width": [10, 10, 10],
        "height": [10, 10, 10],
        "conf": [99, 99, 99],
    }
    assert _boxes_from_tesseract_dict(data) == []


def test_boxes_from_tesseract_dict_drops_zero_size_box():
    data = {
        "text": ["x"],
        "left": [1],
        "top": [1],
        "width": [0],
        "height": [0],
        "conf": [99],
    }
    assert _boxes_from_tesseract_dict(data) == []


def test_build_ocr_engine_raises_when_unavailable():
    """FR-13 variant: tesseract binary missing → ERR_PIXEL_OCR_ENGINE_FAILURE."""
    with pytest.raises(PixelDeidEngineError) as exc:
        build_ocr_engine("tesseract")
    assert exc.value.code == "ERR_PIXEL_OCR_ENGINE_FAILURE"


def test_build_ocr_engine_unknown_name():
    with pytest.raises(PixelDeidEngineError):
        build_ocr_engine("tessa-whatever")


def test_tesseract_empty_languages_rejected():
    eng = TesseractOcrEngine()
    with pytest.raises(PixelDeidEngineError):
        eng.detect_text(None, languages=[])
