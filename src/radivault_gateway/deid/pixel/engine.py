"""Pixel-stage orchestrator (dev-spec §7.1).

Ties triage → OCR redaction → defacing → re-verification gates together.
Always consumes the staged DICOM directory the metadata de-id engine already
wrote; mutates files in-place or replaces them atomically via
``Dataset.save_as``. Heavy imports (pydicom, numpy) are deferred so
``import radivault_gateway.deid.pixel.engine`` never raises on hosts without
the pixel extras.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from radivault_gateway.deid.pixel.config import PixelDeidConfig
from radivault_gateway.deid.pixel.deface_engine import (
    DefaceResult,
    DefacingEngine,
    build_deface_engine,
)
from radivault_gateway.deid.pixel.errors import (
    PixelDeidEngineError,
    PixelQuarantineRequired,
)
from radivault_gateway.deid.pixel.exclusion import MedicalExclusionMatcher
from radivault_gateway.deid.pixel.ocr_engine import (
    OcrBox,
    OcrEngine,
    build_ocr_engine,
)
from radivault_gateway.deid.pixel.redaction import (
    apply_redactions,
    reverify_frame,
)
from radivault_gateway.deid.pixel.triage import (
    TriageDecision,
    TriageResult,
    triage_study,
)

log = logging.getLogger("radivault.pipeline")


@dataclass(frozen=True)
class PixelDeidResult:
    pseudo_study_uid: str
    decision: str  # TriageDecision value
    ocr_applied: bool
    defacing_applied: bool
    n_frames_ocr: int
    n_boxes_redacted: int
    n_volumes_defaced: int
    ocr_duration_ms: int
    deface_duration_ms: int
    library_ocr: str | None
    library_deface: str | None
    removed_voxel_ratio: float = 0.0
    avg_confidence: float = 0.0
    min_confidence: float = 0.0
    max_confidence: float = 0.0
    p10_confidence: float = 0.0
    exclusion_matched: bool = False


class PixelDeidEngine:
    """Public orchestrator. Owns OCR and (optionally) defacing engines."""

    def __init__(
        self,
        cfg: PixelDeidConfig,
        *,
        ocr_engine: OcrEngine | None = None,
        deface_engine: DefacingEngine | None = None,
        fallback_deface_engine: DefacingEngine | None = None,
    ) -> None:
        self._cfg = cfg
        self._ocr = ocr_engine
        self._deface = deface_engine
        self._fallback_deface = fallback_deface_engine
        self._exclusion = MedicalExclusionMatcher(cfg.defacing.exclusion_patterns)

    # ---- public API ----

    def triage(
        self,
        staged_dir: Path,
    ) -> TriageResult:
        return triage_study(
            staged_dir,
            modality_allowlist=self._cfg.ocr.modality_allowlist,
        )

    def process_study(
        self,
        staged_dir: Path,
        *,
        pseudo_study_uid: str,
        study_description: str | None,
        modality_set: set[str],
        body_part: str | None,
    ) -> PixelDeidResult:
        triage_result = self.triage(staged_dir)
        log.info(
            "pixel.triage.decided",
            extra={
                "event": "pixel.triage.decided",
                "pseudo_study_uid": pseudo_study_uid,
                "pixel": {
                    "stage": "triage",
                    "decision": triage_result.decision.value,
                    "reason": triage_result.reason,
                },
            },
        )

        ocr_result: _OcrRunResult | None = None
        if self._should_run_ocr(triage_result):
            ocr_result = self._run_ocr(staged_dir, triage_result)

        # Medical exclusion check (before defacing). OCR has already run so
        # that burn-in text is stripped even when the study is routed to
        # quarantine for clinician review.
        exclusion = self._exclusion.matches(study_description or "")
        if exclusion.matched and self._defacing_eligible(modality_set, body_part):
            raise PixelQuarantineRequired(
                code="ERR_PIXEL_MEDICAL_EXCLUSION",
                reason=f"exclusion_pattern={exclusion.pattern}",
            )

        deface_result: DefaceResult | None = None
        library_deface: str | None = None
        if self._should_run_defacing(modality_set, body_part):
            deface_result, library_deface = self._run_defacing(
                staged_dir, pseudo_study_uid=pseudo_study_uid
            )

        return _build_result(
            pseudo_study_uid=pseudo_study_uid,
            triage_result=triage_result,
            ocr=ocr_result,
            deface=deface_result,
            library_deface=library_deface,
            exclusion_matched=exclusion.matched,
        )

    # ---- helpers ----

    def _should_run_ocr(self, triage_result: TriageResult) -> bool:
        if not self._cfg.ocr.enabled:
            return False
        if self._ocr is None:
            return False
        return triage_result.decision == TriageDecision.OCR_REQUIRED

    def _defacing_eligible(
        self,
        modality_set: set[str],
        body_part: str | None,
    ) -> bool:
        allowed_modalities = set(self._cfg.defacing.modalities)
        allowed_body = set(self._cfg.defacing.body_parts)
        if not modality_set & allowed_modalities:
            return False
        if not body_part:
            return False
        return body_part.upper() in allowed_body

    def _should_run_defacing(
        self,
        modality_set: set[str],
        body_part: str | None,
    ) -> bool:
        if not self._cfg.defacing.enabled:
            return False
        if self._deface is None:
            return False
        return self._defacing_eligible(modality_set, body_part)

    def _run_ocr(
        self,
        staged_dir: Path,
        triage_result: TriageResult,
    ) -> _OcrRunResult:
        """Execute OCR + redaction + residual recheck across all frames."""
        import pydicom

        total_boxes: list[OcrBox] = []
        frames_scanned = 0
        redacted_total = 0
        assert self._ocr is not None
        started = time.monotonic()
        paths = sorted(Path(staged_dir).rglob("*.dcm"))
        for path in paths:
            ds = pydicom.dcmread(path, force=False)
            frames = _iter_frames(ds)
            if not frames:
                continue
            mutated = False
            for frame in frames:
                frames_scanned += 1
                try:
                    boxes = self._ocr.detect_text(frame, languages=list(self._cfg.ocr.languages))
                except PixelDeidEngineError:
                    raise
                except Exception as exc:
                    raise PixelDeidEngineError(
                        "ERR_PIXEL_OCR_ENGINE_FAILURE",
                        f"OCR engine raised: {exc}",
                    ) from exc
                accepted = [b for b in boxes if b.confidence >= self._cfg.ocr.confidence_threshold]
                total_boxes.extend(accepted)
                redaction = apply_redactions(
                    frame,
                    boxes,
                    confidence_threshold=self._cfg.ocr.confidence_threshold,
                    fill_strategy=self._cfg.ocr.redaction_fill,
                    padding_px=self._cfg.ocr.box_padding_px,
                )
                redacted_total += redaction.redacted_count
                if redaction.redacted_count:
                    mutated = True
                if self._cfg.ocr.residual_recheck and accepted:
                    residuals = reverify_frame(
                        frame,
                        accepted,
                        confidence_threshold=self._cfg.ocr.confidence_threshold,
                        padding_px=max(4, self._cfg.ocr.box_padding_px * 2),
                        ocr_engine=self._ocr,
                        languages=list(self._cfg.ocr.languages),
                    )
                    if residuals:
                        raise PixelQuarantineRequired(
                            code="ERR_PIXEL_RESIDUAL_TEXT",
                            reason=f"residual_boxes={len(residuals)}",
                        )
            if mutated:
                _write_frames_back(ds, frames)
                _mark_dicom_pixel_redacted(ds)
                ds.save_as(path, enforce_file_format=False)

        duration_ms = int((time.monotonic() - started) * 1000)
        if triage_result.decision == TriageDecision.OCR_REQUIRED and redacted_total == 0:
            # Burned-in study but we found nothing we trust → quarantine.
            raise PixelQuarantineRequired(
                code="ERR_PIXEL_OCR_LOW_CONFIDENCE",
                reason="no_box_above_threshold",
            )
        confs = [b.confidence for b in total_boxes]
        return _OcrRunResult(
            n_frames_ocr=frames_scanned,
            n_boxes_redacted=redacted_total,
            duration_ms=duration_ms,
            confidences=confs,
            engine_name=self._ocr.engine_name,
            engine_version=self._ocr.version(),
        )

    def _run_defacing(
        self,
        staged_dir: Path,
        *,
        pseudo_study_uid: str,
    ) -> tuple[DefaceResult | None, str | None]:
        assert self._deface is not None
        candidate = _pick_defacing_volume(staged_dir)
        if candidate is None:
            return None, None
        out_path = candidate.with_suffix(".defaced.nii.gz")
        try:
            result = self._deface.deface_volume(candidate, out_path)
        except PixelDeidEngineError as exc:
            if (
                self._cfg.defacing.fallback
                and self._fallback_deface is not None
                and self._fallback_deface.is_available()
            ):
                log.warning(
                    "pixel.deface.fallback_used",
                    extra={
                        "event": "pixel.deface.fallback_used",
                        "pixel": {
                            "stage": "deface",
                            "error_code": exc.code,
                            "fallback_library": self._fallback_deface.engine_name,
                        },
                    },
                )
                try:
                    result = self._fallback_deface.deface_volume(candidate, out_path)
                except PixelDeidEngineError:
                    raise PixelQuarantineRequired(
                        code="ERR_PIXEL_DEFACE_FAILURE",
                        reason="fallback_failed",
                    ) from exc
                library = self._fallback_deface.engine_name
            else:
                raise PixelQuarantineRequired(
                    code="ERR_PIXEL_DEFACE_FAILURE",
                    reason=exc.code,
                ) from exc
        else:
            library = self._deface.engine_name
        if (
            self._cfg.defacing.residual_voxel_check
            and result.removed_voxel_ratio < self._cfg.defacing.min_removed_ratio
        ):
            raise PixelQuarantineRequired(
                code="ERR_PIXEL_RESIDUAL_FACE_VOXELS",
                reason=(
                    f"removed_voxel_ratio={result.removed_voxel_ratio:.4f} "
                    f"< {self._cfg.defacing.min_removed_ratio:.4f}"
                ),
            )
        # AC-28 / dev-spec §6.4: stamp every DICOM in the study with the
        # defacing de-identification method tags so downstream consumers can
        # tell the study has been defaced. We mark all staged files because
        # the defaced 3D volume was reconstructed from the series and the
        # tags are study-level provenance (FR-18).
        _stamp_defacing_tags(staged_dir)
        return result, library


@dataclass(frozen=True)
class _OcrRunResult:
    n_frames_ocr: int
    n_boxes_redacted: int
    duration_ms: int
    confidences: list[float]
    engine_name: str
    engine_version: str


def _iter_frames(ds) -> list:
    """Return a list of per-frame ndarrays for a DICOM dataset.

    Missing pixel data or unsupported transfer syntaxes return an empty list;
    the caller treats this as "no-op" rather than an error.
    """
    try:
        arr = ds.pixel_array  # type: ignore[attr-defined]
    except Exception:
        return []
    # numpy.ndarray attribute access doesn't raise here; ``arr`` can be 2D or 3D.
    if arr is None:
        return []
    import numpy as np  # type: ignore[import-not-found]

    if isinstance(arr, np.ndarray) and arr.ndim == 3:
        return [arr[i] for i in range(arr.shape[0])]
    return [arr]


def _write_frames_back(ds, frames) -> None:
    """Write ``frames`` back into ``ds.PixelData``. 2D-single-frame only in v0.2."""
    import numpy as np  # type: ignore[import-not-found]

    if not frames:
        return
    arr = np.asarray(frames[0]) if len(frames) == 1 else np.stack(frames, axis=0)
    ds.PixelData = arr.tobytes()
    if arr.ndim == 3:
        ds.NumberOfFrames = int(arr.shape[0])


def _mark_dicom_pixel_redacted(ds) -> None:
    """Append pixel-redaction DICOM tags (dev-spec §6.4, FR-18)."""
    from pydicom.dataset import Dataset

    existing = getattr(ds, "DeidentificationMethod", "") or ""
    if "PixelRedacted" not in existing:
        suffix = " + PixelRedacted" if existing else "PixelRedacted"
        ds.DeidentificationMethod = existing + suffix
    seq = list(getattr(ds, "DeidentificationMethodCodeSequence", []) or [])
    codes = {getattr(item, "CodeValue", None) for item in seq}
    if "113101" not in codes:
        item = Dataset()
        item.CodeValue = "113101"
        item.CodingSchemeDesignator = "DCM"
        item.CodeMeaning = "Pixel Data Modified"
        seq.append(item)
        ds.DeidentificationMethodCodeSequence = seq
    comment = str(getattr(ds, "ImageComments", "") or "").strip()
    tag = "RadiVault-PixelRedacted"
    if tag not in comment:
        ds.ImageComments = (comment + f" {tag}").strip()


def _mark_dicom_defaced(ds) -> None:
    """Append defacing DICOM tags (dev-spec §6.4)."""
    from pydicom.dataset import Dataset

    existing = getattr(ds, "DeidentificationMethod", "") or ""
    if "Defaced" not in existing:
        suffix = " + Defaced" if existing else "Defaced"
        ds.DeidentificationMethod = existing + suffix
    seq = list(getattr(ds, "DeidentificationMethodCodeSequence", []) or [])
    codes = {getattr(item, "CodeValue", None) for item in seq}
    if "RV_DEFACE_01" not in codes:
        item = Dataset()
        item.CodeValue = "RV_DEFACE_01"
        item.CodingSchemeDesignator = "RADIVAULT"
        item.CodeMeaning = "3D Face Surface Defaced"
        seq.append(item)
        ds.DeidentificationMethodCodeSequence = seq
    comment = str(getattr(ds, "ImageComments", "") or "").strip()
    tag = "RadiVault-Defaced"
    if tag not in comment:
        ds.ImageComments = (comment + f" {tag}").strip()


def _stamp_defacing_tags(staged_dir: Path) -> None:
    """AC-28 / FR-18: append defacing tags to every DICOM under ``staged_dir``.

    Called on successful defacing return paths (primary library or fallback).
    Failures to open an individual DICOM are logged and skipped rather than
    aborting the whole study — the study has already been defaced in the
    pixel domain and partial tag updates are safer than a crash.
    """
    import pydicom

    for path in sorted(Path(staged_dir).rglob("*.dcm")):
        try:
            ds = pydicom.dcmread(path, force=False)
        except Exception as exc:
            log.warning(
                "pixel.deface.mark_tag_skipped",
                extra={
                    "event": "pixel.deface.mark_tag_skipped",
                    "pixel": {"stage": "deface", "path": str(path), "error": str(exc)},
                },
            )
            continue
        _mark_dicom_defaced(ds)
        ds.save_as(path, enforce_file_format=False)


def _pick_defacing_volume(staged_dir: Path) -> Path | None:  # pragma: no cover - live only
    """Stub: choose the densest series volume for pydeface.

    v0.2 implementation is live-only (requires dcm2niix/nibabel at runtime);
    unit tests inject mocked DefacingEngine instances so this helper is not
    exercised. Returns ``None`` when no candidate could be formed.
    """
    candidates = sorted(Path(staged_dir).rglob("*.dcm"))
    if not candidates:
        return None
    return candidates[0]


def _build_result(
    *,
    pseudo_study_uid: str,
    triage_result: TriageResult,
    ocr: _OcrRunResult | None,
    deface: DefaceResult | None,
    library_deface: str | None,
    exclusion_matched: bool,
) -> PixelDeidResult:
    confs = ocr.confidences if ocr else []
    if confs:
        srt = sorted(confs)
        avg_c = sum(srt) / len(srt)
        p10 = srt[max(0, int(0.1 * len(srt)) - 1)] if len(srt) > 0 else 0.0
        min_c = srt[0]
        max_c = srt[-1]
    else:
        avg_c = p10 = min_c = max_c = 0.0
    return PixelDeidResult(
        pseudo_study_uid=pseudo_study_uid,
        decision=triage_result.decision.value,
        ocr_applied=ocr is not None and ocr.n_boxes_redacted > 0,
        defacing_applied=deface is not None,
        n_frames_ocr=ocr.n_frames_ocr if ocr else 0,
        n_boxes_redacted=ocr.n_boxes_redacted if ocr else 0,
        n_volumes_defaced=1 if deface is not None else 0,
        ocr_duration_ms=ocr.duration_ms if ocr else 0,
        deface_duration_ms=deface.duration_ms if deface else 0,
        library_ocr=ocr.engine_name if ocr else None,
        library_deface=library_deface,
        removed_voxel_ratio=float(deface.removed_voxel_ratio) if deface else 0.0,
        avg_confidence=avg_c,
        min_confidence=min_c,
        max_confidence=max_c,
        p10_confidence=p10,
        exclusion_matched=exclusion_matched,
    )


def build_pixel_deid_engine(cfg: PixelDeidConfig) -> PixelDeidEngine | None:
    """Factory used by the pipeline (FR-41).

    Returns ``None`` when ``cfg.enabled=False`` so the orchestrator skips the
    pixel stage entirely and v0.1 bit-equivalence is preserved.
    """
    if not cfg.enabled:
        return None

    ocr_engine: OcrEngine | None = None
    if cfg.ocr.enabled:
        try:
            ocr_engine = build_ocr_engine(cfg.ocr.engine)
        except PixelDeidEngineError as exc:
            # FR-44: OCR is mandatory when enabled. Re-raise with the
            # cfg-flavoured code so the CLI can translate to exit 64.
            raise PixelDeidEngineError(
                "ERR_CFG_PIXEL_ENGINE_MISSING",
                f"{cfg.ocr.engine} unavailable: {exc.message}",
            ) from exc

    deface_engine: DefacingEngine | None = None
    fallback_engine: DefacingEngine | None = None
    if cfg.defacing.enabled:
        try:
            engine = build_deface_engine(cfg.defacing.library)
            if engine.is_available():
                deface_engine = engine
            elif cfg.defacing.on_missing == "disable":
                deface_engine = None
            else:
                raise PixelDeidEngineError(
                    "ERR_PIXEL_DEFACE_LIBRARY_MISSING",
                    f"{cfg.defacing.library} not available and on_missing=fail_start",
                )
            if cfg.defacing.fallback:
                other = "mridefacer" if cfg.defacing.library == "pydeface" else "pydeface"
                try:
                    fb = build_deface_engine(other)
                    fallback_engine = fb if fb.is_available() else None
                except PixelDeidEngineError:
                    fallback_engine = None
        except PixelDeidEngineError:
            if cfg.defacing.on_missing == "fail_start":
                raise
            deface_engine = None

    return PixelDeidEngine(
        cfg,
        ocr_engine=ocr_engine,
        deface_engine=deface_engine,
        fallback_deface_engine=fallback_engine,
    )


def box_hash(text: str) -> str:
    """Return ``sha256:xxxxxxxx....xxxx`` hash for CLI --show-boxes (FR-38)."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
