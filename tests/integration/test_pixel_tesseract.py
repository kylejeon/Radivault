"""Live Tesseract integration (dev-spec §14.2).

Skipped by default. Gated by ``PIXEL_TEST_TESSERACT=1`` and the presence of
both the ``tesseract`` binary on PATH and the ``pytesseract`` wrapper in the
runtime environment. Run via:

    PIXEL_TEST_TESSERACT=1 pytest tests/integration/test_pixel_tesseract.py -q

The test exercises end-to-end burn-in OCR + redaction on a synthetic
PNG-rendered DICOM surrogate so we never ship real PHI.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path  # noqa: F401 — kept for hint clarity in skipped runs

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("PIXEL_TEST_TESSERACT") != "1",
        reason="set PIXEL_TEST_TESSERACT=1 to run live Tesseract integration",
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("pytesseract") is None
        or importlib.util.find_spec("PIL") is None
        or importlib.util.find_spec("numpy") is None,
        reason="pytesseract / Pillow / numpy not installed",
    ),
]


def test_tesseract_detects_english_burn_in():  # pragma: no cover - live only
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    from radivault_gateway.deid.pixel.ocr_engine import TesseractOcrEngine

    img = Image.new("L", (400, 120), color=0)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    draw.text((20, 40), "PATIENT NAME", fill=255, font=font)
    arr = np.array(img, dtype="uint8")

    engine = TesseractOcrEngine()
    boxes = engine.detect_text(arr, languages=["eng"])
    assert any(b.confidence >= 0.60 for b in boxes)


def test_tesseract_redaction_roundtrip_passes_reverify():  # pragma: no cover - live only
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    from radivault_gateway.deid.pixel.ocr_engine import TesseractOcrEngine
    from radivault_gateway.deid.pixel.redaction import (
        apply_redactions,
        reverify_frame,
    )

    img = Image.new("L", (400, 120), color=0)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    draw.text((20, 40), "SECRET NAME", fill=255, font=font)
    arr = np.array(img, dtype="uint8")

    engine = TesseractOcrEngine()
    boxes = engine.detect_text(arr, languages=["eng"])
    apply_redactions(arr, boxes, confidence_threshold=0.6, padding_px=4)
    residuals = reverify_frame(
        arr,
        boxes,
        confidence_threshold=0.6,
        padding_px=4,
        ocr_engine=engine,
        languages=["eng"],
    )
    assert residuals == []
