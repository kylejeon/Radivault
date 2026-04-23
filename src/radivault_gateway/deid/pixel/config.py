"""Pydantic v2 models for ``deid.pixel.*`` (dev-spec §6.3, FR-40..FR-44).

Master kill-switch is :attr:`PixelDeidConfig.enabled`; default **OFF**. When
disabled, validation of nested engine/library strings is relaxed so operators
can keep stale config snippets without breaking startup.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_EXCLUSION_PATTERNS: tuple[str, ...] = (
    r"(?i)dental",
    r"(?i)\bENT\b",
    r"(?i)facial[ _-]?trauma",
    r"(?i)maxillofacial",
    r"(?i)sinus",
    r"(?i)orbit",
    r"(?i)ophthalm",
)

DEFAULT_OCR_MODALITY_ALLOWLIST: tuple[str, ...] = ("SC", "OT", "US", "XA", "MG")
DEFAULT_DEFACE_MODALITIES: tuple[str, ...] = ("CT", "MR")
DEFAULT_DEFACE_BODY_PARTS: tuple[str, ...] = ("HEAD", "BRAIN", "NEURO", "STROKE")


class PixelOcrConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    engine: Literal["tesseract", "paddleocr"] = "tesseract"
    languages: list[str] = Field(
        default_factory=lambda: ["kor", "eng"],
        description="Tesseract language packs, e.g. ['kor', 'eng'].",
    )
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    redaction_fill: Literal["solid_black", "mean_pixel", "gaussian_blur"] = "solid_black"
    box_padding_px: int = Field(default=2, ge=0, le=64)
    residual_recheck: bool = True
    modality_allowlist: list[str] = Field(
        default_factory=lambda: list(DEFAULT_OCR_MODALITY_ALLOWLIST)
    )

    @field_validator("languages")
    @classmethod
    def _languages_nonempty(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value if isinstance(v, str) and v.strip()]
        if not cleaned:
            raise ValueError("deid.pixel.ocr.languages must be a non-empty string list")
        return cleaned

    @field_validator("modality_allowlist")
    @classmethod
    def _modality_upper(cls, value: list[str]) -> list[str]:
        return [m.strip().upper() for m in value if isinstance(m, str) and m.strip()]


class PixelDefacingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    library: Literal["pydeface", "mridefacer"] = "pydeface"
    fallback: bool = True
    on_missing: Literal["disable", "fail_start"] = "disable"
    modalities: list[str] = Field(default_factory=lambda: list(DEFAULT_DEFACE_MODALITIES))
    body_parts: list[str] = Field(default_factory=lambda: list(DEFAULT_DEFACE_BODY_PARTS))
    exclusion_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUSION_PATTERNS))
    min_removed_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    residual_voxel_check: bool = True

    @field_validator("modalities", "body_parts")
    @classmethod
    def _upper_list(cls, value: list[str]) -> list[str]:
        return [m.strip().upper() for m in value if isinstance(m, str) and m.strip()]

    @field_validator("exclusion_patterns")
    @classmethod
    def _patterns_compilable(cls, value: list[str]) -> list[str]:
        import re

        for pat in value:
            try:
                re.compile(pat)
            except re.error as exc:
                raise ValueError(f"invalid regex {pat!r}: {exc}") from exc
        return value


class PixelDeidConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    quarantine_on_failure: bool = True
    ocr: PixelOcrConfig = Field(default_factory=PixelOcrConfig)
    defacing: PixelDefacingConfig = Field(default_factory=PixelDefacingConfig)

    @model_validator(mode="after")
    def _noop_when_disabled(self) -> PixelDeidConfig:
        # When disabled, we still keep the nested fields but validation is
        # sufficient. No extra checks required.
        return self
