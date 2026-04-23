"""De-ID pixel-stage package (v0.2, opt-in).

Burn-in OCR redaction + 3D defacing. Heavy dependencies (pytesseract,
pydeface, nibabel, etc.) are imported lazily by the concrete engine
implementations. Importing this package itself must never raise.

See ``docs/specs/dev-spec-de-id-pixel.md`` and ``docs/specs/design-spec-de-id-pixel.md``.
"""

from __future__ import annotations

from radivault_gateway.deid.pixel.config import (
    PixelDefacingConfig,
    PixelDeidConfig,
    PixelOcrConfig,
)
from radivault_gateway.deid.pixel.engine import (
    PixelDeidEngine,
    PixelDeidResult,
    box_hash,
    build_pixel_deid_engine,
)
from radivault_gateway.deid.pixel.errors import (
    ERROR_MESSAGES,
    PixelDeidEngineError,
    PixelQuarantineRequired,
    format_cli_error,
)
from radivault_gateway.deid.pixel.exclusion import (
    ExclusionMatch,
    MedicalExclusionMatcher,
)
from radivault_gateway.deid.pixel.ocr_engine import (
    OcrBox,
    OcrEngine,
    build_ocr_engine,
)
from radivault_gateway.deid.pixel.redaction import (
    RedactionResult,
    apply_redactions,
    reverify_frame,
)
from radivault_gateway.deid.pixel.triage import (
    TriageDecision,
    TriageResult,
    triage_datasets,
    triage_study,
)

__all__ = [
    "ERROR_MESSAGES",
    "ExclusionMatch",
    "MedicalExclusionMatcher",
    "OcrBox",
    "OcrEngine",
    "PixelDefacingConfig",
    "PixelDeidConfig",
    "PixelDeidEngine",
    "PixelDeidEngineError",
    "PixelDeidResult",
    "PixelOcrConfig",
    "PixelQuarantineRequired",
    "RedactionResult",
    "TriageDecision",
    "TriageResult",
    "apply_redactions",
    "box_hash",
    "build_ocr_engine",
    "build_pixel_deid_engine",
    "format_cli_error",
    "reverify_frame",
    "triage_datasets",
    "triage_study",
]
