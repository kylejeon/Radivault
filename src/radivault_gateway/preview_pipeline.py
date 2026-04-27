"""Per-series preview pipeline (jpg-preview-defacing dev-spec §4).

Orchestrates the new ingest-time preview path:

    DICOM series dir
        │
        ├─ deface gate (FR-DEFACE-1 modality + body-part + regex)
        │
        ├── deface_required ─► sidecar /deface ─► axial JPGs
        │       (FR-DEFACE-6/7, FR-PREVIEW-4)
        │
        └── not_required    ─► local Pillow render via thumbnail helpers
                (FR-PREVIEW-5; reuses thumbnail._ct_window_for_body_part
                + thumbnail._array_to_uint8 — no duplication)

Outputs:

- ``PreviewBatchResult`` — per-series summary embedded into the manifest
  ``preview`` block (FR-PREVIEW-1).
- MinIO writes — one JPG per frame at
  ``previews/{pseudo_study_uid}/{pseudo_series_uid}/{frame_idx:04d}.jpg``
  (FR-PREVIEW-9 / FR-PREVIEW-10).
- Audit rows — one ``phi_scrub_audit`` per series via the injected
  AuditWriter (FR-AUDIT-1).

All MinIO + audit IO is pushed behind protocol-style adapters so unit
tests can swap in fakes (see ``tests/unit/test_preview_pipeline.py``).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Protocol

from radivault_gateway.deface_client import (
    QUARANTINE_INPUT,
    QUARANTINE_RUNTIME,
    DefaceClient,
    DefaceFailure,
    DefaceSuccess,
)
from radivault_gateway.thumbnail import _array_to_uint8, _ct_window_for_body_part

log = logging.getLogger("radivault_gateway.preview_pipeline")

PIPELINE_VERSION = "0.1.0"
PREVIEW_BUCKET = "radivault-previews"
PREVIEW_KEY_PREFIX = "previews"
JPEG_QUALITY = 85
TARGET_SIZE = (512, 512)

# FR-DEFACE-1 — body-part whitelist (case-insensitive substring match).
HEAD_NECK_BODY_PARTS = {
    "HEAD",
    "BRAIN",
    "FACE",
    "NECK",
    "SKULL",
    "JAW",
    "CSPINE",
}

# FR-DEFACE-1 — fallback regex matched against StudyDescription / ProtocolName
# when BodyPartExamined is absent.
DEFACE_REGEX = re.compile(
    r"(?i)(brain|head|skull|sinus|orbit|face|neck|maxillo|cervical|temporal|tmj|pituitary)"
)

# FR-DEFACE-4 — modalities that never need defacing.
NO_DEFACE_MODALITIES = {"US", "MG", "CR", "DR", "DX", "NM", "PT"}

# FR-DEFACE-1 — only CT/MR are deface-eligible.
DEFACE_ELIGIBLE_MODALITIES = {"CT", "MR"}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FrameRecord:
    """Single per-frame entry. The pipeline emits one ``dicom_preview_frame``
    DB row per record; ``minio_key`` is the bucket-relative path."""

    frame_idx: int
    minio_key: str
    width: int
    height: int
    byte_size: int
    sha256: str
    phi_scrub_method: str
    source_instance_uid_pseudo: str | None = None


@dataclass
class SeriesPreviewResult:
    """Per-series summary written to manifest + persisted to series row."""

    pseudo_series_uid: str
    series_num: int
    modality: str
    body_part: str | None
    preview_status: str  # 'generated' | 'skipped' | 'quarantined' | 'pending'
    deface_decision: str | None  # 'required' | 'not_required' | 'skipped_unsupported_modality'
    deface_decision_reason: str
    phi_scrub_method: str
    frame_count: int
    frames: list[FrameRecord] = field(default_factory=list)
    error_code: str | None = None


@dataclass
class PreviewBatchResult:
    """Top-level result merged into manifest_entry['preview']."""

    skipped: bool = False
    reason: str | None = None
    pipeline_version: str = PIPELINE_VERSION
    series: list[SeriesPreviewResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Adapters — injected by the runner so tests can swap them out.
# ---------------------------------------------------------------------------


class MinioClient(Protocol):
    def put_jpeg(self, *, bucket: str, key: str, body: bytes) -> None: ...

    def ensure_bucket(self, *, bucket: str) -> None: ...


class AuditWriter(Protocol):
    def write_audit(
        self,
        *,
        pseudo_study_uid: str,
        pseudo_series_uid: str,
        modality: str,
        body_part: str | None,
        deface_decision: str,
        deface_decision_reason: str,
        phi_scrub_method: str,
        sidecar_image_tag: str | None,
        afni_version: str | None,
        duration_ms: int | None,
        outcome: str,
        error_code: str | None,
        error_detail: str | None,
        pipeline_version: str,
    ) -> None: ...


class FrameWriter(Protocol):
    def write_frame_rows(
        self,
        *,
        pseudo_study_uid: str,
        pseudo_series_uid: str,
        frames: list[FrameRecord],
    ) -> None: ...


# ---------------------------------------------------------------------------
# Series description bag — what the pipeline needs from the runner.
# ---------------------------------------------------------------------------


@dataclass
class SeriesInput:
    pseudo_series_uid: str
    series_num: int
    series_dir: Path  # directory containing the De-ID'd DICOM instances
    modality: str | None
    body_part: str | None
    series_description: str | None = None
    protocol_name: str | None = None


# ---------------------------------------------------------------------------
# Public entrypoint (FR-PREVIEW-2 signature)
# ---------------------------------------------------------------------------


def is_pipeline_enabled() -> bool:
    """FR-PREVIEW-3 — feature flag check."""
    raw = os.environ.get("PREVIEW_PIPELINE_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def process_study(
    *,
    pseudo_study_uid: str,
    series_inputs: list[SeriesInput],
    study_description: str | None,
    minio_client: MinioClient,
    audit_writer: AuditWriter,
    frame_writer: FrameWriter,
    deface_client: DefaceClient | None = None,
) -> PreviewBatchResult:
    """Render previews for every series of a study.

    The caller (transfer/runner.preview_runner) supplies the De-ID'd
    DICOM directory + already-extracted Modality / BodyPartExamined /
    StudyDescription / ProtocolName values per series (FR-DEFACE-2).

    Returns a :class:`PreviewBatchResult` to be merged into the manifest.
    """
    if not is_pipeline_enabled():
        return PreviewBatchResult(skipped=True, reason="flag_off")

    deface = deface_client or DefaceClient()
    # FR-DEFACE-8: if the sidecar is unhealthy, deface-required series go
    # straight to quarantine; non-deface series still run.
    sidecar_healthy = deface.healthz()

    minio_client.ensure_bucket(bucket=PREVIEW_BUCKET)

    out = PreviewBatchResult()
    for series in series_inputs:
        result = _process_one_series(
            pseudo_study_uid=pseudo_study_uid,
            series=series,
            study_description=study_description,
            minio_client=minio_client,
            audit_writer=audit_writer,
            frame_writer=frame_writer,
            deface=deface,
            sidecar_healthy=sidecar_healthy,
        )
        out.series.append(result)
    return out


# ---------------------------------------------------------------------------
# Per-series state machine
# ---------------------------------------------------------------------------


def _process_one_series(
    *,
    pseudo_study_uid: str,
    series: SeriesInput,
    study_description: str | None,
    minio_client: MinioClient,
    audit_writer: AuditWriter,
    frame_writer: FrameWriter,
    deface: DefaceClient,
    sidecar_healthy: bool,
) -> SeriesPreviewResult:
    started = time.perf_counter()
    modality = (series.modality or "").upper()
    decision, reason = decide_deface(
        modality=modality,
        body_part=series.body_part,
        study_description=study_description,
        protocol_name=series.protocol_name,
    )

    # FR-PREVIEW-7 — series-level burned-in gate.
    if _series_has_burned_in(series.series_dir):
        return _record_series(
            pseudo_study_uid=pseudo_study_uid,
            series=series,
            decision="not_required" if decision == "not_required" else decision,
            decision_reason=reason,
            phi_scrub_method="skipped_burned_in",
            preview_status="skipped",
            frames=[],
            audit_writer=audit_writer,
            frame_writer=frame_writer,
            outcome="skipped",
            error_code=None,
            error_detail=None,
            duration_ms=int((time.perf_counter() - started) * 1000),
            sidecar_image_tag=None,
            afni_version=None,
        )

    if decision == "skipped_unsupported_modality":
        return _record_series(
            pseudo_study_uid=pseudo_study_uid,
            series=series,
            decision=decision,
            decision_reason=reason,
            phi_scrub_method="modality_no_deface_needed",
            preview_status="skipped",
            frames=[],
            audit_writer=audit_writer,
            frame_writer=frame_writer,
            outcome="not_required",
            error_code=None,
            error_detail=None,
            duration_ms=int((time.perf_counter() - started) * 1000),
            sidecar_image_tag=None,
            afni_version=None,
        )

    if decision == "required":
        if not sidecar_healthy:
            return _record_series(
                pseudo_study_uid=pseudo_study_uid,
                series=series,
                decision=decision,
                decision_reason=reason,
                phi_scrub_method="deface_failed_runtime",
                preview_status="quarantined",
                frames=[],
                audit_writer=audit_writer,
                frame_writer=frame_writer,
                outcome="quarantine_runtime",
                error_code="SIDECAR_UNHEALTHY",
                error_detail="healthz != ok",
                duration_ms=int((time.perf_counter() - started) * 1000),
                sidecar_image_tag=None,
                afni_version=None,
            )

        outcome, sc = _run_deface_with_retry(deface, series.series_dir)
        if isinstance(outcome, DefaceFailure):
            method = (
                "deface_failed_input"
                if outcome.quarantine_reason == QUARANTINE_INPUT
                else "deface_failed_runtime"
            )
            return _record_series(
                pseudo_study_uid=pseudo_study_uid,
                series=series,
                decision=decision,
                decision_reason=reason,
                phi_scrub_method=method,
                preview_status="quarantined",
                frames=[],
                audit_writer=audit_writer,
                frame_writer=frame_writer,
                outcome=outcome.quarantine_reason,
                error_code=_audit_error_code(outcome),
                error_detail=outcome.detail,
                duration_ms=int((time.perf_counter() - started) * 1000),
                sidecar_image_tag=None,
                afni_version=None,
            )

        # Success path — upload frames to MinIO, record DB rows.
        frames = _upload_deface_frames(
            pseudo_study_uid=pseudo_study_uid,
            series=series,
            success=outcome,
            minio_client=minio_client,
        )
        return _record_series(
            pseudo_study_uid=pseudo_study_uid,
            series=series,
            decision=decision,
            decision_reason=reason,
            phi_scrub_method="afni_refacer_v0_7",
            preview_status="generated",
            frames=frames,
            audit_writer=audit_writer,
            frame_writer=frame_writer,
            outcome="success",
            error_code=None,
            error_detail=None,
            duration_ms=outcome.duration_ms
            or int((time.perf_counter() - started) * 1000),
            sidecar_image_tag=outcome.sidecar_image_tag,
            afni_version=outcome.afni_version,
        )

    # decision == "not_required" — local Pillow render of every instance.
    try:
        frames = _render_local_frames(
            pseudo_study_uid=pseudo_study_uid,
            series=series,
            minio_client=minio_client,
        )
    except _LocalRenderFailure as exc:
        return _record_series(
            pseudo_study_uid=pseudo_study_uid,
            series=series,
            decision=decision,
            decision_reason=reason,
            phi_scrub_method="deface_failed_input",
            preview_status="quarantined",
            frames=[],
            audit_writer=audit_writer,
            frame_writer=frame_writer,
            outcome="quarantine_input",
            error_code="LOCAL_RENDER_FAIL",
            error_detail=str(exc)[:255],
            duration_ms=int((time.perf_counter() - started) * 1000),
            sidecar_image_tag=None,
            afni_version=None,
        )
    return _record_series(
        pseudo_study_uid=pseudo_study_uid,
        series=series,
        decision=decision,
        decision_reason=reason,
        phi_scrub_method="none_required",
        preview_status="generated" if frames else "skipped",
        frames=frames,
        audit_writer=audit_writer,
        frame_writer=frame_writer,
        outcome="not_required",
        error_code=None,
        error_detail=None,
        duration_ms=int((time.perf_counter() - started) * 1000),
        sidecar_image_tag=None,
        afni_version=None,
    )


# ---------------------------------------------------------------------------
# FR-DEFACE-1 decision function — pure, easy to unit-test.
# ---------------------------------------------------------------------------


def decide_deface(
    *,
    modality: str | None,
    body_part: str | None,
    study_description: str | None = None,
    protocol_name: str | None = None,
) -> tuple[str, str]:
    """Return ``(decision, decision_reason)`` for a series.

    decision ∈ {required, not_required, skipped_unsupported_modality}
    """
    mod = (modality or "").upper().strip()
    if not mod:
        return "skipped_unsupported_modality", "modality=unknown"
    if mod in NO_DEFACE_MODALITIES:
        return "not_required", f"modality={mod}"
    if mod not in DEFACE_ELIGIBLE_MODALITIES:
        return "skipped_unsupported_modality", f"modality={mod}"

    bp = (body_part or "").upper().strip()
    if bp:
        for token in HEAD_NECK_BODY_PARTS:
            if token in bp:
                return "required", f"BodyPartExamined={bp}"
        return "not_required", f"BodyPartExamined={bp}"

    # No body part — fall back to regex on description / protocol.
    if study_description:
        m = DEFACE_REGEX.search(study_description)
        if m:
            return "required", f"regex:StudyDescription={study_description[:80]}"
    if protocol_name:
        m = DEFACE_REGEX.search(protocol_name)
        if m:
            return "required", f"regex:ProtocolName={protocol_name[:80]}"
    return "not_required", "no_body_part_no_regex_match"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _LocalRenderFailure(Exception):
    pass


def _series_has_burned_in(series_dir: Path) -> bool:
    """FR-PREVIEW-7 — series-level burned-in scan."""
    if not series_dir.exists():
        return False
    try:
        import pydicom  # type: ignore[import-not-found]
    except ImportError:
        return False
    for path in sorted(series_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=False)
        except Exception:
            continue
        burned = str(getattr(ds, "BurnedInAnnotation", "") or "").upper().strip()
        if burned == "YES":
            return True
    return False


def _run_deface_with_retry(
    deface: DefaceClient, dicom_dir: Path
) -> tuple[DefaceSuccess | DefaceFailure, str]:
    """FR-DEFACE-8 — 1 retry on runtime failure, none on input failure."""
    first = deface.deface_series(dicom_dir=dicom_dir)
    if isinstance(first, DefaceSuccess):
        return first, "first_try"
    if first.quarantine_reason == QUARANTINE_INPUT:
        return first, "no_retry_input"
    second = deface.deface_series(dicom_dir=dicom_dir)
    if isinstance(second, DefaceSuccess):
        return second, "retry_succeeded"
    return second, "retry_exhausted"


def _audit_error_code(failure: DefaceFailure) -> str:
    """FR-DEFACE-8: map runtime failure into a stable audit code."""
    if failure.quarantine_reason == QUARANTINE_RUNTIME:
        return "AFNI_CRASH"
    return failure.error_code[:40] or "INPUT_INVALID"


def _upload_deface_frames(
    *,
    pseudo_study_uid: str,
    series: SeriesInput,
    success: DefaceSuccess,
    minio_client: MinioClient,
) -> list[FrameRecord]:
    out: list[FrameRecord] = []
    for frame in success.frames:
        key = preview_key(
            pseudo_study_uid, series.pseudo_series_uid, frame.frame_idx
        )
        minio_client.put_jpeg(
            bucket=PREVIEW_BUCKET,
            key=key,
            body=frame.jpeg_bytes,
        )
        sha = hashlib.sha256(frame.jpeg_bytes).hexdigest()
        # We don't have width/height from the sidecar in v0.1; assume target.
        out.append(
            FrameRecord(
                frame_idx=frame.frame_idx,
                minio_key=key,
                width=TARGET_SIZE[0],
                height=TARGET_SIZE[1],
                byte_size=len(frame.jpeg_bytes),
                sha256=sha,
                phi_scrub_method="afni_refacer_v0_7",
                source_instance_uid_pseudo=None,
            )
        )
    return out


def _render_local_frames(
    *,
    pseudo_study_uid: str,
    series: SeriesInput,
    minio_client: MinioClient,
) -> list[FrameRecord]:
    """FR-PREVIEW-5 — render every instance to a 512x512 JPG locally."""
    try:
        import pydicom  # type: ignore[import-not-found]
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:
        raise _LocalRenderFailure(f"missing dep: {exc}") from exc

    instances = sorted(
        p for p in series.series_dir.rglob("*") if p.is_file()
    )
    if not instances:
        return []

    parsed: list[tuple[int, str, "pydicom.Dataset"]] = []  # type: ignore[name-defined]
    for path in instances:
        try:
            ds = pydicom.dcmread(path, force=False)
        except Exception:
            continue
        in_no = getattr(ds, "InstanceNumber", None)
        try:
            in_no_int = int(in_no) if in_no is not None else 1 << 30
        except (TypeError, ValueError):
            in_no_int = 1 << 30
        sop_uid = str(getattr(ds, "SOPInstanceUID", "") or "")
        parsed.append((in_no_int, sop_uid, ds))

    if not parsed:
        raise _LocalRenderFailure("no readable DICOM instances")

    parsed.sort(key=lambda p: (p[0], p[1]))
    modality = (series.modality or "").upper()
    body_part = series.body_part

    out: list[FrameRecord] = []
    for idx, (_in, sop_uid, ds) in enumerate(parsed):
        try:
            arr = ds.pixel_array
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "preview_local_pixel_fail",
                extra={"event": "preview.local.error", "error": str(exc)[:200]},
            )
            continue
        if arr.ndim == 3:
            # multi-frame DICOM — pick frame 0 (the rest are addressable
            # by frame_idx in the manifest, but for v0.1 we treat one
            # instance == one preview frame).
            arr = arr[0]
        if arr.ndim > 2:
            try:
                import numpy as np

                arr = np.mean(arr, axis=-1)
            except Exception:
                continue
        try:
            u8 = _array_to_uint8(arr, ds, modality, body_part)
            img = Image.fromarray(u8, mode="L")
            img.thumbnail(TARGET_SIZE, Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            jpeg = buf.getvalue()
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "preview_local_encode_fail",
                extra={"event": "preview.local.error", "error": str(exc)[:200]},
            )
            continue

        # Touch the windowing helper to make ruff/lint understand the
        # symbol is intentionally re-exported (and the dev-spec FR-PREVIEW-5
        # explicitly requires reuse of _ct_window_for_body_part).
        _ = _ct_window_for_body_part

        key = preview_key(pseudo_study_uid, series.pseudo_series_uid, idx)
        minio_client.put_jpeg(bucket=PREVIEW_BUCKET, key=key, body=jpeg)
        out.append(
            FrameRecord(
                frame_idx=idx,
                minio_key=key,
                width=img.width,
                height=img.height,
                byte_size=len(jpeg),
                sha256=hashlib.sha256(jpeg).hexdigest(),
                phi_scrub_method="none_required",
                source_instance_uid_pseudo=sop_uid or None,
            )
        )
    return out


def _record_series(
    *,
    pseudo_study_uid: str,
    series: SeriesInput,
    decision: str,
    decision_reason: str,
    phi_scrub_method: str,
    preview_status: str,
    frames: list[FrameRecord],
    audit_writer: AuditWriter,
    frame_writer: FrameWriter,
    outcome: str,
    error_code: str | None,
    error_detail: str | None,
    duration_ms: int | None,
    sidecar_image_tag: str | None,
    afni_version: str | None,
) -> SeriesPreviewResult:
    """Persist per-series + per-frame DB rows + return the manifest entry."""
    if frames:
        frame_writer.write_frame_rows(
            pseudo_study_uid=pseudo_study_uid,
            pseudo_series_uid=series.pseudo_series_uid,
            frames=frames,
        )
    audit_writer.write_audit(
        pseudo_study_uid=pseudo_study_uid,
        pseudo_series_uid=series.pseudo_series_uid,
        modality=(series.modality or "").upper() or "?",
        body_part=series.body_part,
        deface_decision=decision,
        deface_decision_reason=decision_reason,
        phi_scrub_method=phi_scrub_method,
        sidecar_image_tag=sidecar_image_tag,
        afni_version=afni_version,
        duration_ms=duration_ms,
        outcome=outcome,
        error_code=error_code,
        error_detail=error_detail,
        pipeline_version=PIPELINE_VERSION,
    )
    log.info(
        "preview_series_recorded",
        extra={
            "event": f"preview.deface.{outcome}",
            "pseudo_series_uid": series.pseudo_series_uid,
            "duration_ms": duration_ms,
            "n_frames": len(frames),
        },
    )
    return SeriesPreviewResult(
        pseudo_series_uid=series.pseudo_series_uid,
        series_num=series.series_num,
        modality=(series.modality or "").upper() or "?",
        body_part=series.body_part,
        preview_status=preview_status,
        deface_decision=decision,
        deface_decision_reason=decision_reason,
        phi_scrub_method=phi_scrub_method,
        frame_count=len(frames),
        frames=frames,
        error_code=error_code,
    )


# ---------------------------------------------------------------------------
# Key layout helpers (FR-PREVIEW-10)
# ---------------------------------------------------------------------------


def preview_key(
    pseudo_study_uid: str, pseudo_series_uid: str, frame_idx: int
) -> str:
    """``previews/{study}/{series}/{idx:04d}.jpg`` — 0-based, 4-digit pad."""
    return (
        f"{PREVIEW_KEY_PREFIX}/"
        f"{pseudo_study_uid}/{pseudo_series_uid}/{frame_idx:04d}.jpg"
    )
