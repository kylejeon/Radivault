"""Pixel-stage error taxonomy (dev-spec §13, design-spec §5.1).

Eight ERR codes + one WARN + one startup-time CFG code. Every code carries a
paired Korean/English message and a ``suggested_action`` suitable for CLI
surfaces. ``doc_url`` is built from the canonical ``/gateway-agent/errors/``
route used by the v0.1 error taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

_DOC_BASE = "https://docs.radivault.io/gateway-agent/errors"


@dataclass(frozen=True)
class PixelErrorMessage:
    code: str
    ko: str
    en: str
    suggested_action: str
    log_level: str  # INFO | WARN | ERROR

    @property
    def doc_url(self) -> str:
        return f"{_DOC_BASE}/{self.code}"


ERROR_MESSAGES: dict[str, PixelErrorMessage] = {
    "ERR_PIXEL_OCR_LOW_CONFIDENCE": PixelErrorMessage(
        code="ERR_PIXEL_OCR_LOW_CONFIDENCE",
        ko="OCR 신뢰도가 임계 미만이어서 스터디를 격리합니다.",
        en="OCR confidence below threshold; study routed to quarantine.",
        suggested_action=(
            "deid.pixel.ocr.confidence_threshold 재검토 또는 PaddleOCR 엔진으로 전환 검토."
        ),
        log_level="WARN",
    ),
    "ERR_PIXEL_OCR_ENGINE_FAILURE": PixelErrorMessage(
        code="ERR_PIXEL_OCR_ENGINE_FAILURE",
        ko="OCR 엔진 실행 중 내부 오류가 발생했습니다.",
        en="OCR engine internal failure.",
        suggested_action=("pixel-selftest 실행으로 바이너리/언어팩 확인. -pixel 이미지 사용 확인."),
        log_level="ERROR",
    ),
    "ERR_PIXEL_RESIDUAL_TEXT": PixelErrorMessage(
        code="ERR_PIXEL_RESIDUAL_TEXT",
        ko="마스킹 후 잔여 텍스트가 탐지되어 스터디를 격리합니다.",
        en="Residual text detected after redaction; study quarantined.",
        suggested_action=(
            "deid.pixel.ocr.box_padding_px 상향(2→4) 또는 redaction_fill=solid_black 유지."
        ),
        log_level="ERROR",
    ),
    "ERR_PIXEL_DEFACE_LIBRARY_MISSING": PixelErrorMessage(
        code="ERR_PIXEL_DEFACE_LIBRARY_MISSING",
        ko="Defacing 라이브러리(pydeface)를 찾을 수 없습니다.",
        en="Defacing library (pydeface) not available.",
        suggested_action=(
            "-pixel 이미지 사용 확인 또는 deid.pixel.defacing.enabled=false. "
            "on_missing=disable(기본)이면 자동 다운그레이드."
        ),
        log_level="WARN",
    ),
    "ERR_PIXEL_DEFACE_FAILURE": PixelErrorMessage(
        code="ERR_PIXEL_DEFACE_FAILURE",
        ko="Defacing 처리 중 런타임 오류가 발생했습니다.",
        en="Defacing runtime error.",
        suggested_action=(
            "deid.pixel.defacing.fallback=true로 mridefacer 폴백 허용. "
            "반복 발생 시 지원팀에 샘플 송부."
        ),
        log_level="ERROR",
    ),
    "ERR_PIXEL_RESIDUAL_FACE_VOXELS": PixelErrorMessage(
        code="ERR_PIXEL_RESIDUAL_FACE_VOXELS",
        ko="Defacing 후 얼굴 복셀이 임계 이상 잔존하여 격리합니다.",
        en="Residual face voxels exceed threshold after defacing; quarantined.",
        suggested_action=(
            "deid.pixel.defacing.min_removed_ratio 재평가. 반복 발생 시 폴백 엔진으로 재시도."
        ),
        log_level="ERROR",
    ),
    "ERR_PIXEL_MEDICAL_EXCLUSION": PixelErrorMessage(
        code="ERR_PIXEL_MEDICAL_EXCLUSION",
        ko="의료 제외 리스트(치과/ENT/안과 등)에 해당하여 격리합니다.",
        en="Study matches medical exclusion list; routed to quarantine.",
        suggested_action=(
            "임상 자문 후 사람이 업로드 여부 결정. 오탐이면 exclusion_patterns 조정."
        ),
        log_level="INFO",
    ),
    "WARN_PIXEL_HEURISTIC_TRIGGER": PixelErrorMessage(
        code="WARN_PIXEL_HEURISTIC_TRIGGER",
        ko="휴리스틱 사전검사가 번인 가능성을 감지했습니다(v0.2.1에서 활성).",
        en="Heuristic pre-scan suggests burn-in (enabled in v0.2.1).",
        suggested_action="v0.2에서는 No-op 경고. v0.2.1에서 실제 구현.",
        log_level="WARN",
    ),
    "ERR_CFG_PIXEL_ENGINE_MISSING": PixelErrorMessage(
        code="ERR_CFG_PIXEL_ENGINE_MISSING",
        ko="설정에서 픽셀 처리를 활성화했으나 엔진 바이너리가 없습니다.",
        en="Pixel enabled in config but engine binary absent.",
        suggested_action=("이미지 태그를 :0.2.0-pixel 로 전환 또는 deid.pixel.enabled=false."),
        log_level="ERROR",
    ),
}


class PixelDeidEngineError(Exception):
    """Raised by pixel engine when OCR/defacing internals fail.

    The orchestrator decides whether to escalate to quarantine based on
    ``cfg.deid.pixel.quarantine_on_failure`` (default true).
    """

    DEFAULT_CODE: ClassVar[str] = "ERR_PIXEL_OCR_ENGINE_FAILURE"

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = (
            message
            or ERROR_MESSAGES.get(
                code,
                PixelErrorMessage(
                    code=code,
                    ko="픽셀 엔진 내부 오류",
                    en="Pixel engine internal error",
                    suggested_action="",
                    log_level="ERROR",
                ),
            ).en
        )
        super().__init__(f"[{code}] {self.message}")


class PixelQuarantineRequired(Exception):
    """Raised when a study must be routed to the v0.1 quarantine path.

    Covers triage giving up, re-verification failure, medical-exclusion hits,
    and low-confidence OCR when no box clears the threshold.
    """

    def __init__(
        self,
        code: str,
        reason: str | None = None,
        offending_sops: list[str] | None = None,
    ) -> None:
        self.code = code
        self.reason = reason or code.lower()
        self.offending_sops = offending_sops or []
        msg = ERROR_MESSAGES.get(code)
        text = msg.en if msg else code
        super().__init__(f"[{code}] {text}")


def format_cli_error(code: str, **fields: str) -> str:
    """Render an error using the 5-field template (design-spec §5.2)."""
    msg = ERROR_MESSAGES[code]
    lines = [f"[{msg.code}] {msg.ko} / {msg.en}"]
    for key, value in fields.items():
        lines.append(f"  {key:<12}: {value}")
    if msg.suggested_action:
        lines.append(f"  수정 / Fix : {msg.suggested_action}")
    lines.append(f"  문서 / Docs: {msg.doc_url}")
    return "\n".join(lines)
