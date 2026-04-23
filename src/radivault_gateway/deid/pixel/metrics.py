"""Prometheus metrics for the v0.2 de-id-pixel stage.

Implements design-spec §4.3 AC-D-12: the 10 ``radivault_gateway_pixel_*``
metrics (7 counters + 3 histograms + 1 redaction-region histogram).
Gateway has no HTTP ``/metrics`` server in v0.2; operators snapshot via
``radivault-gateway metrics dump``.

Using a dedicated ``CollectorRegistry`` so (a) metrics are discoverable in
isolation and (b) the gateway process does not pollute the default
``prometheus_client`` REGISTRY (which stays free for any future Gateway-wide
metric wiring).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

# Histogram bucket defaults (design-spec §4.3 notes: OCR ≤ 60s p95,
# defacing ≤ 120s p95, removed_voxel_ratio 0..1, ocr_confidence 0..1).
_OCR_DURATION_BUCKETS: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0)
_DEFACE_DURATION_BUCKETS: tuple[float, ...] = (
    1.0,
    5.0,
    15.0,
    30.0,
    60.0,
    90.0,
    120.0,
    180.0,
    300.0,
    600.0,
)
_CONFIDENCE_BUCKETS: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
_RATIO_BUCKETS: tuple[float, ...] = (0.0, 0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0)
_REDACTION_BUCKETS: tuple[float, ...] = (0.0, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0)


@dataclass
class PixelMetrics:
    """All 10 pixel-stage metrics registered on a single ``CollectorRegistry``."""

    registry: CollectorRegistry
    studies_total: Counter
    ocr_duration_seconds: Histogram
    deface_duration_seconds: Histogram
    ocr_confidence: Histogram
    ocr_redaction_regions: Histogram
    deface_removed_voxel_ratio: Histogram
    residual_text_found_total: Counter
    residual_face_voxels_total: Counter
    engine_unavailable_total: Counter
    medical_exclusion_hit_total: Counter


def build_pixel_metrics(registry: CollectorRegistry | None = None) -> PixelMetrics:
    """Create and register all 10 pixel metrics (design-spec §4.3)."""
    reg = registry if registry is not None else CollectorRegistry()
    studies_total = Counter(
        "radivault_gateway_pixel_studies_total",
        "Pixel-stage study outcomes by stage and result.",
        labelnames=("stage", "result"),
        registry=reg,
    )
    ocr_duration = Histogram(
        "radivault_gateway_pixel_ocr_duration_seconds",
        "OCR processing duration per study (seconds).",
        labelnames=("engine",),
        buckets=_OCR_DURATION_BUCKETS,
        registry=reg,
    )
    deface_duration = Histogram(
        "radivault_gateway_pixel_deface_duration_seconds",
        "Defacing processing duration per volume (seconds).",
        labelnames=("library",),
        buckets=_DEFACE_DURATION_BUCKETS,
        registry=reg,
    )
    ocr_confidence = Histogram(
        "radivault_gateway_pixel_ocr_confidence",
        "OCR box-level confidence distribution (0..1).",
        buckets=_CONFIDENCE_BUCKETS,
        registry=reg,
    )
    ocr_redaction_regions = Histogram(
        "radivault_gateway_pixel_ocr_redaction_regions",
        "Redaction box count per study.",
        buckets=_REDACTION_BUCKETS,
        registry=reg,
    )
    deface_ratio = Histogram(
        "radivault_gateway_pixel_deface_removed_voxel_ratio",
        "Ratio of face voxels removed per volume (0..1).",
        buckets=_RATIO_BUCKETS,
        registry=reg,
    )
    residual_text = Counter(
        "radivault_gateway_pixel_residual_text_found_total",
        "Residual text boxes found during re-verification OCR. >0 is CRITICAL.",
        registry=reg,
    )
    residual_face = Counter(
        "radivault_gateway_pixel_residual_face_voxels_total",
        "Residual face voxel checks that failed the min_removed_ratio gate.",
        registry=reg,
    )
    engine_unavailable = Counter(
        "radivault_gateway_pixel_engine_unavailable_total",
        "Engine invocation failures (binary missing, module import error, crash).",
        labelnames=("engine",),
        registry=reg,
    )
    medical_exclusion = Counter(
        "radivault_gateway_pixel_medical_exclusion_hit_total",
        "Medical exclusion pattern hits on StudyDescription.",
        labelnames=("reason",),
        registry=reg,
    )
    return PixelMetrics(
        registry=reg,
        studies_total=studies_total,
        ocr_duration_seconds=ocr_duration,
        deface_duration_seconds=deface_duration,
        ocr_confidence=ocr_confidence,
        ocr_redaction_regions=ocr_redaction_regions,
        deface_removed_voxel_ratio=deface_ratio,
        residual_text_found_total=residual_text,
        residual_face_voxels_total=residual_face,
        engine_unavailable_total=engine_unavailable,
        medical_exclusion_hit_total=medical_exclusion,
    )


def record_triage_decision(metrics: PixelMetrics | None, decision: str) -> None:
    if metrics is None:
        return
    metrics.studies_total.labels(stage="triage", result=decision).inc()


def record_ocr(
    metrics: PixelMetrics | None,
    *,
    engine: str,
    duration_seconds: float,
    redaction_count: int,
    confidences: list[float],
    success: bool,
) -> None:
    if metrics is None:
        return
    metrics.ocr_duration_seconds.labels(engine=engine).observe(max(0.0, float(duration_seconds)))
    metrics.ocr_redaction_regions.observe(max(0, int(redaction_count)))
    for c in confidences:
        if c is None:
            continue
        metrics.ocr_confidence.observe(max(0.0, min(1.0, float(c))))
    metrics.studies_total.labels(stage="ocr", result="success" if success else "fail").inc()


def record_defacing(
    metrics: PixelMetrics | None,
    *,
    library: str,
    duration_seconds: float,
    removed_voxel_ratio: float,
    success: bool,
) -> None:
    if metrics is None:
        return
    metrics.deface_duration_seconds.labels(library=library).observe(
        max(0.0, float(duration_seconds))
    )
    metrics.deface_removed_voxel_ratio.observe(max(0.0, min(1.0, float(removed_voxel_ratio))))
    metrics.studies_total.labels(stage="deface", result="success" if success else "fail").inc()


def record_residual_text(metrics: PixelMetrics | None, count: int = 1) -> None:
    if metrics is None:
        return
    metrics.residual_text_found_total.inc(max(0, int(count)))


def record_residual_face(metrics: PixelMetrics | None, count: int = 1) -> None:
    if metrics is None:
        return
    metrics.residual_face_voxels_total.inc(max(0, int(count)))


def record_engine_unavailable(metrics: PixelMetrics | None, *, engine: str) -> None:
    if metrics is None:
        return
    metrics.engine_unavailable_total.labels(engine=engine).inc()


def record_medical_exclusion(metrics: PixelMetrics | None, *, reason: str) -> None:
    if metrics is None:
        return
    metrics.medical_exclusion_hit_total.labels(reason=reason).inc()


def record_quarantine(metrics: PixelMetrics | None, *, stage: str) -> None:
    """Generic ``stage`` quarantine counter increment."""
    if metrics is None:
        return
    metrics.studies_total.labels(stage=stage, result="quarantine").inc()


def dump_text(metrics: PixelMetrics) -> str:
    """Render the registry in Prometheus exposition format."""
    return generate_latest(metrics.registry).decode("utf-8")


def dump_dict(metrics: PixelMetrics) -> dict[str, Any]:
    """Render the registry as a JSON-serialisable dict for CLI --format text."""
    out: dict[str, Any] = {}
    for family in metrics.registry.collect():
        samples: list[dict[str, Any]] = []
        for sample in family.samples:
            samples.append(
                {
                    "name": sample.name,
                    "labels": dict(sample.labels),
                    "value": sample.value,
                }
            )
        out[family.name] = {
            "type": family.type,
            "help": family.documentation,
            "samples": samples,
        }
    return out
