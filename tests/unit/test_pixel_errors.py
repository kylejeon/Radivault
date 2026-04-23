"""Error taxonomy tests (dev-spec §13, design-spec §5.1)."""

from __future__ import annotations

import pytest

from radivault_gateway.deid.pixel.errors import (
    ERROR_MESSAGES,
    PixelDeidEngineError,
    PixelQuarantineRequired,
    format_cli_error,
)

REQUIRED_CODES = {
    "ERR_PIXEL_OCR_LOW_CONFIDENCE",
    "ERR_PIXEL_OCR_ENGINE_FAILURE",
    "ERR_PIXEL_RESIDUAL_TEXT",
    "ERR_PIXEL_DEFACE_LIBRARY_MISSING",
    "ERR_PIXEL_DEFACE_FAILURE",
    "ERR_PIXEL_RESIDUAL_FACE_VOXELS",
    "ERR_PIXEL_MEDICAL_EXCLUSION",
    "WARN_PIXEL_HEURISTIC_TRIGGER",
    "ERR_CFG_PIXEL_ENGINE_MISSING",
}


def test_all_required_codes_present():
    assert REQUIRED_CODES.issubset(ERROR_MESSAGES.keys())


def test_every_code_has_ko_en_action_and_doc_url():
    for code, msg in ERROR_MESSAGES.items():
        assert msg.ko, code
        assert msg.en, code
        # WARN_PIXEL_HEURISTIC_TRIGGER is explicitly a design-placeholder; its
        # ``suggested_action`` content is "no-op" text and is allowed to be
        # minimal. All other codes must carry guidance.
        if not code.startswith("WARN_"):
            assert msg.suggested_action, code
        assert msg.doc_url.endswith(code)


def test_quarantine_exception_carries_code():
    exc = PixelQuarantineRequired(code="ERR_PIXEL_RESIDUAL_TEXT", reason="test")
    assert exc.code == "ERR_PIXEL_RESIDUAL_TEXT"
    assert "ERR_PIXEL_RESIDUAL_TEXT" in str(exc)


def test_engine_error_with_unknown_code_still_renders():
    exc = PixelDeidEngineError("ERR_SOMETHING_CUSTOM", "custom message")
    assert exc.code == "ERR_SOMETHING_CUSTOM"
    assert "custom message" in str(exc)


def test_format_cli_error_includes_doc_link():
    rendered = format_cli_error(
        "ERR_PIXEL_RESIDUAL_TEXT",
        frames_affected="2",
    )
    assert "ERR_PIXEL_RESIDUAL_TEXT" in rendered
    assert "frames_affected" in rendered
    assert rendered.strip().endswith("/errors/ERR_PIXEL_RESIDUAL_TEXT")


def test_format_cli_error_missing_code_raises():
    with pytest.raises(KeyError):
        format_cli_error("ERR_DOES_NOT_EXIST")
