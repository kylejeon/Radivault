"""AFNI refacer sidecar — FR-DEFACE-6 / FR-DEFACE-7 contract.

A minimal FastAPI app exposing one job endpoint and one healthcheck:

    GET  /healthz
    POST /deface  (multipart form: dicom_tar, mode, timeout_s)

Runtime sequence inside ``/deface`` (FR-DEFACE-7):
    1. dcm2niix the incoming DICOM tar -> NIfTI.
    2. ``@afni_refacer_run -mode_deface`` -> defaced NIfTI.
    3. nibabel load -> axial slices -> Pillow JPEG q85 grayscale 512x512
       (EXIF/ICC stripped).
    4. Pack JPGs into a tar + return alongside the defaced NIfTI and a
       JSON report.

Errors map to the dev-spec status codes:
    400 invalid_input        -> dicom_tar missing / unparseable
    422 unprocessable_dicom  -> dcm2niix or AFNI rejected the volume
    500 afni_crashed         -> AFNI subprocess crashed
    504 timeout              -> per-call timeout exceeded
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import subprocess
import tarfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

log = logging.getLogger("afni_refacer_sidecar")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(title="afni-refacer-sidecar", version="0.1.0")


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict[str, str]:
    afni_version = _afni_version()
    return {
        "status": "ok",
        "afni_version": afni_version or "unknown",
        "image_tag": os.environ.get("SIDECAR_IMAGE_TAG", "radivault/deface-sidecar:0.1.0"),
    }


# ---------------------------------------------------------------------------
# /deface
# ---------------------------------------------------------------------------


@app.post("/deface")
async def deface(
    dicom_tar: UploadFile = File(...),
    mode: str = Form("deface"),
    timeout_s: int = Form(600),
) -> StreamingResponse:
    if mode != "deface":
        # FR-DEFACE-6: only mode_deface is permitted in v0.1 (refacer
        # mode is out-of-scope per dev-spec §3).
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_input", "detail": f"unsupported mode={mode!r}"},
        )

    job_id = uuid.uuid4().hex
    workdir = Path("/tmp") / f"deface-{job_id}"
    in_dir = workdir / "in"
    nii_dir = workdir / "nii"
    out_dir = workdir / "out"
    for d in (in_dir, nii_dir, out_dir):
        d.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    try:
        tar_bytes = await dicom_tar.read()
        if not tar_bytes:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "invalid_input", "detail": "empty dicom_tar"},
            )

        # Step 0 — extract DICOM tar.
        try:
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
                tf.extractall(in_dir)
        except (tarfile.TarError, OSError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "invalid_input", "detail": f"tar error: {exc}"},
            ) from exc

        # Step 1 — dcm2niix.
        try:
            _run(
                ["dcm2niix", "-z", "y", "-o", str(nii_dir), str(in_dir)],
                timeout=min(timeout_s, 120),
            )
        except subprocess.CalledProcessError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "unprocessable_dicom",
                    "detail": f"dcm2niix exited {exc.returncode}",
                },
            ) from exc

        nii_files = sorted(nii_dir.glob("*.nii.gz"))
        if not nii_files:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "unprocessable_dicom",
                    "detail": "dcm2niix produced no NIfTI",
                },
            )
        nii_in = nii_files[0]

        # Step 2 — AFNI @afni_refacer_run -mode_deface.
        # MAJOR-1 fix: include the .nii.gz suffix in -prefix so AFNI emits
        # a deterministic filename (defaced.deface.nii.gz / defaced.nii.gz)
        # that _resolve_afni_output's exact-match branch (1/3) catches. This
        # prevents the parent.glob("*.nii.gz") fallback from accidentally
        # selecting a non-defaced side-output (e.g. defaced.face.nii.gz —
        # the *face mask* — which would expose a non-defaced volume).
        prefix = out_dir / "defaced.nii.gz"
        try:
            _run(
                [
                    "@afni_refacer_run",
                    "-input",
                    str(nii_in),
                    "-mode_deface",
                    "-prefix",
                    str(prefix),
                    "-overwrite",
                ],
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=504,
                detail={"error_code": "timeout", "detail": f"AFNI exceeded {timeout_s}s"},
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "afni_crashed",
                    "detail": f"AFNI exited {exc.returncode}",
                },
            ) from exc

        defaced_path = _resolve_afni_output(prefix)
        if defaced_path is None:
            raise HTTPException(
                status_code=500,
                detail={"error_code": "afni_crashed", "detail": "no defaced NIfTI emitted"},
            )

        # Step 3 — render axial JPGs.
        jpg_tar_bytes, n_frames = _render_axial_jpgs(defaced_path)

        # Step 4 — pack response multipart.
        report = {
            "n_frames": n_frames,
            "afni_version": _afni_version(),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "warning": None,
        }
        return _multipart_response(
            defaced_nifti=defaced_path.read_bytes(),
            axial_jpgs_tar=jpg_tar_bytes,
            report=report,
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — last-resort; report scrubbed
        log.exception("sidecar_unhandled")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "afni_crashed",
                "detail": f"unhandled: {type(exc).__name__}",
            },
        ) from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess:
    log.info("sidecar_subprocess", extra={"event": "sidecar.cmd", "argv0": cmd[0]})
    return subprocess.run(
        cmd,
        check=True,
        timeout=timeout,
        capture_output=True,
    )


def _afni_version() -> str | None:
    try:
        r = subprocess.run(
            ["afni", "-ver"], capture_output=True, text=True, timeout=10, check=False
        )
        if r.returncode == 0:
            return r.stdout.strip().splitlines()[0][:64] or None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return None


def _resolve_afni_output(prefix: Path) -> Path | None:
    """AFNI emits ``<prefix>.deface.nii.gz`` or ``<prefix>+orig.HEAD/BRIK``.
    We only consume the .nii.gz form.

    The caller may pass the prefix either with or without a trailing
    ``.nii.gz`` suffix (we standardise on *with* per the MAJOR-1 fix so
    that AFNI emits a deterministic filename). We normalise to a bare
    stem first so the probe order — (1) ``<stem>.deface.nii.gz`` first,
    then (3) ``<stem>.nii.gz`` — stays exactly what callers and tests
    have always relied on.
    """
    prefix_str = str(prefix)
    stem_str = (
        prefix_str[: -len(".nii.gz")]
        if prefix_str.endswith(".nii.gz")
        else prefix_str
    )
    for cand in (
        Path(stem_str + ".deface.nii.gz"),
        Path(stem_str + ".deface.nii.gz"),
        Path(stem_str + ".nii.gz"),
    ):
        if cand.exists():
            return cand
    # Fallback: scan parent for any .nii.gz, EXCLUDING AFNI side outputs.
    # ``@afni_refacer_run`` may emit auxiliary volumes like
    # ``*.face.nii.gz`` (the face mask — i.e. the *region to be zeroed*),
    # ``*.skullstrip.nii.gz``, and ``*.mask.nii.gz``. None of these are the
    # defaced volume; selecting one here would silently expose an
    # un-defaced or wholly-wrong NIfTI to the gateway. With the .nii.gz
    # suffix on -prefix the exact-match branches above always win, but we
    # keep this defence-in-depth in case the prefix convention regresses.
    parent = prefix.parent
    if parent.exists():
        candidates = sorted(
            p
            for p in parent.glob("*.nii.gz")
            if not p.name.endswith(
                (".face.nii.gz", ".skullstrip.nii.gz", ".mask.nii.gz")
            )
        )
        if candidates:
            return candidates[0]
    return None


def _render_axial_jpgs(nifti_path: Path) -> tuple[bytes, int]:
    import nibabel as nib  # type: ignore[import-untyped]
    import numpy as np
    from PIL import Image

    img = nib.load(str(nifti_path))
    arr = img.get_fdata()
    if arr.ndim < 3:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "unprocessable_dicom",
                "detail": f"defaced volume has ndim={arr.ndim}",
            },
        )
    # Axial axis convention for nibabel-loaded NIfTI is the last spatial
    # axis (index 2). We rotate 90deg so radiological-convention up == sup.
    n_frames = arr.shape[2]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for k in range(n_frames):
            sl = arr[:, :, k]
            sl_u8 = _normalise_u8(sl)
            sl_rot = np.rot90(sl_u8)
            pil = Image.fromarray(sl_rot, mode="L")
            pil.thumbnail((512, 512), Image.LANCZOS)
            jpg_buf = io.BytesIO()
            pil.save(jpg_buf, format="JPEG", quality=85, optimize=True)
            data = jpg_buf.getvalue()
            info = tarfile.TarInfo(name=f"{k:04d}.jpg")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue(), n_frames


def _normalise_u8(slice_arr: Any) -> Any:
    import numpy as np

    arr = slice_arr.astype("float32", copy=False)
    lo = float(np.percentile(arr, 1))
    hi = float(np.percentile(arr, 99))
    if hi <= lo:
        return np.zeros(arr.shape, dtype="uint8")
    arr = (arr - lo) / (hi - lo) * 255.0
    return np.clip(arr, 0, 255).astype("uint8")


def _multipart_response(
    *, defaced_nifti: bytes, axial_jpgs_tar: bytes, report: dict[str, Any]
) -> StreamingResponse:
    """Pack {nifti, jpg_tar, report.json} as a multipart/mixed body.

    Format per FR-DEFACE-6: ``defaced_nifti`` + ``axial_jpgs.tar`` +
    ``report.json``. We use a fixed boundary so the gateway client can
    parse without re-discovery.
    """
    boundary = "rv-deface-1d4f0c9c"
    parts: list[bytes] = []

    def _part(name: str, content_type: str, body: bytes) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"\r\n'
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            ).encode()
        )
        parts.append(body)
        parts.append(b"\r\n")

    _part("defaced_nifti", "application/gzip", defaced_nifti)
    _part("axial_jpgs.tar", "application/x-tar", axial_jpgs_tar)
    _part("report.json", "application/json", json.dumps(report).encode())
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }

    def _stream():
        yield body

    return StreamingResponse(_stream(), status_code=200, headers=headers)


# ---------------------------------------------------------------------------
# Error envelope formatting — make HTTPException emit FR-DEFACE-6 shape.
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
def _http_exc_handler(_req, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": "invalid_input", "detail": str(exc.detail)},
    )
