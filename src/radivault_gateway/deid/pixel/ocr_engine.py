"""OCR engine Protocol + Tesseract and PaddleOCR implementations (dev-spec §4.2).

The implementations guard their heavy imports (``pytesseract``, ``paddleocr``)
so the module can always be imported. Unit tests use :class:`OcrEngine` via
Protocol satisfaction with in-memory fakes; integration tests exercise the real
``TesseractOcrEngine``.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from radivault_gateway.deid.pixel.errors import PixelDeidEngineError

if TYPE_CHECKING:  # pragma: no cover - typing only
    import numpy as np  # type: ignore[import-not-found]

log = logging.getLogger("radivault.pipeline")


@dataclass(frozen=True)
class OcrBox:
    """Single OCR detection.

    ``text`` is engine-internal only. MUST NOT be logged as plaintext
    (dev-spec FR-38). The orchestrator hashes the text when emitting
    audit/CLI output.
    """

    x: int
    y: int
    w: int
    h: int
    text: str
    confidence: float


@runtime_checkable
class OcrEngine(Protocol):
    """Abstract OCR engine contract.

    Implementations must be pickle-safe? No — the v0.2 orchestrator is single
    process; pickling is not required. Implementations must be safe to call
    from multiple frames in sequence.
    """

    engine_name: str

    def detect_text(
        self,
        image: np.ndarray,
        *,
        languages: list[str],
    ) -> list[OcrBox]: ...

    def version(self) -> str: ...


class TesseractOcrEngine:
    """Tesseract 5 implementation via ``pytesseract`` (FR-8)."""

    engine_name: str = "tesseract"

    def __init__(self, *, confidence_threshold: float = 0.0) -> None:
        self._threshold = confidence_threshold
        self._version_cache: str | None = None

    @staticmethod
    def is_available() -> bool:
        """Whether the ``tesseract`` binary is on PATH AND pytesseract imports."""
        try:
            import pytesseract  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return False
        return shutil.which("tesseract") is not None

    def version(self) -> str:
        if self._version_cache:
            return self._version_cache
        try:
            import pytesseract  # type: ignore[import-not-found]

            ver = str(pytesseract.get_tesseract_version())
        except Exception:
            ver = "unknown"
        self._version_cache = ver
        return ver

    def detect_text(
        self,
        image: np.ndarray,
        *,
        languages: list[str],
    ) -> list[OcrBox]:
        if not languages:
            raise PixelDeidEngineError(
                "ERR_PIXEL_OCR_ENGINE_FAILURE",
                "no OCR languages configured",
            )
        try:
            import pytesseract  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PixelDeidEngineError(
                "ERR_PIXEL_OCR_ENGINE_FAILURE",
                f"pytesseract not installed: {exc}",
            ) from exc
        lang = "+".join(languages)
        try:
            data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
        except Exception as exc:
            raise PixelDeidEngineError(
                "ERR_PIXEL_OCR_ENGINE_FAILURE",
                f"tesseract invocation failed: {exc}",
            ) from exc
        return _boxes_from_tesseract_dict(data)


class PaddleOcrEngine:
    """PaddleOCR implementation (FR-9).

    Only selected when ``deid.pixel.ocr.engine=paddleocr``. The current
    implementation is a thin adapter over ``paddleocr.PaddleOCR``.
    """

    engine_name: str = "paddleocr"

    def __init__(self) -> None:
        self._engine = None
        self._version_cache: str | None = None

    @staticmethod
    def is_available() -> bool:
        try:
            import paddleocr  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return False
        return True

    def version(self) -> str:
        if self._version_cache:
            return self._version_cache
        try:
            import paddleocr  # type: ignore[import-not-found]

            self._version_cache = getattr(paddleocr, "__version__", "unknown")
        except Exception:
            self._version_cache = "unknown"
        return self._version_cache

    def detect_text(
        self,
        image: np.ndarray,
        *,
        languages: list[str],
    ) -> list[OcrBox]:
        try:
            import paddleocr  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PixelDeidEngineError(
                "ERR_PIXEL_OCR_ENGINE_FAILURE",
                f"paddleocr not installed: {exc}",
            ) from exc
        lang = "korean" if any(lg.startswith("kor") for lg in languages) else "en"
        if self._engine is None:
            self._engine = paddleocr.PaddleOCR(  # pragma: no cover - live only
                lang=lang, use_angle_cls=False, use_gpu=False
            )
        try:
            raw = self._engine.ocr(image)  # pragma: no cover - live only
        except Exception as exc:
            raise PixelDeidEngineError(
                "ERR_PIXEL_OCR_ENGINE_FAILURE",
                f"paddleocr invocation failed: {exc}",
            ) from exc
        return _boxes_from_paddle(raw)  # pragma: no cover


def _boxes_from_tesseract_dict(data: dict) -> list[OcrBox]:
    boxes: list[OcrBox] = []
    texts = data.get("text", [])
    lefts = data.get("left", [])
    tops = data.get("top", [])
    widths = data.get("width", [])
    heights = data.get("height", [])
    confs = data.get("conf", [])
    for idx, text in enumerate(texts):
        text_str = str(text or "").strip()
        if not text_str:
            continue
        try:
            raw_conf = float(confs[idx])
        except (KeyError, ValueError, IndexError):
            continue
        # pytesseract returns conf as 0..100 (or -1 when unreliable).
        if raw_conf < 0:
            continue
        normalised = raw_conf / 100.0 if raw_conf > 1.0 else raw_conf
        try:
            x, y, w, h = (
                int(lefts[idx]),
                int(tops[idx]),
                int(widths[idx]),
                int(heights[idx]),
            )
        except (KeyError, ValueError, IndexError):
            continue
        if w <= 0 or h <= 0:
            continue
        boxes.append(OcrBox(x=x, y=y, w=w, h=h, text=text_str, confidence=normalised))
    return boxes


def _boxes_from_paddle(raw: list) -> list[OcrBox]:  # pragma: no cover - live only
    out: list[OcrBox] = []
    if not raw:
        return out
    page = raw[0] if isinstance(raw[0], list) else raw
    for entry in page:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        poly, (text, conf) = entry[0], entry[1]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x = int(min(xs))
        y = int(min(ys))
        w = int(max(xs) - x)
        h = int(max(ys) - y)
        out.append(OcrBox(x=x, y=y, w=w, h=h, text=str(text), confidence=float(conf)))
    return out


def build_ocr_engine(engine_name: str) -> OcrEngine:
    """Factory used by the orchestrator.

    Raises :class:`PixelDeidEngineError` with
    ``ERR_PIXEL_OCR_ENGINE_FAILURE`` when the configured engine's runtime
    dependencies are not available. Operators see this message via
    ``pixel-selftest``.
    """
    if engine_name == "tesseract":
        if not TesseractOcrEngine.is_available():
            raise PixelDeidEngineError(
                "ERR_PIXEL_OCR_ENGINE_FAILURE",
                "tesseract binary not on PATH or pytesseract missing",
            )
        return TesseractOcrEngine()
    if engine_name == "paddleocr":
        if not PaddleOcrEngine.is_available():
            raise PixelDeidEngineError(
                "ERR_PIXEL_OCR_ENGINE_FAILURE",
                "paddleocr not installed",
            )
        return PaddleOcrEngine()
    raise PixelDeidEngineError(
        "ERR_PIXEL_OCR_ENGINE_FAILURE",
        f"unknown OCR engine {engine_name!r}",
    )
