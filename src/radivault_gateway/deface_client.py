"""HTTP client for the AFNI defacing sidecar.

dev-spec-jpg-preview-defacing FR-DEFACE-6 / FR-DEFACE-7 / FR-DEFACE-8.

The sidecar is reached over the docker-compose internal network at
``http://deface-sidecar:8090`` (configurable via ``DEFACE_SIDECAR_URL``).
We never call out to the public internet from this client; the
preview_pipeline orchestrates all retry / quarantine logic on top.

Wire format
-----------
- Request:  multipart/form-data {dicom_tar (tar bytes), mode="deface", timeout_s=int}
- Response: multipart/form-data {defaced_nifti, axial_jpgs.tar, report.json}
  on 200, or JSON envelope on 4xx/5xx.

Why a thin wrapper instead of httpx form posting at the call site
-----------------------------------------------------------------
The pipeline emits per-series and needs to (1) tar a directory, (2) post,
(3) parse a multipart response, (4) classify HTTP status into
``DefaceQuarantineReason``. Centralising that here keeps the pipeline
free of HTTP details and makes it trivial to inject a fake client in
unit tests.
"""

from __future__ import annotations

import io
import logging
import os
import tarfile
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_default_policy
from pathlib import Path

log = logging.getLogger("radivault_gateway.deface_client")

# Public quarantine reasons — pipeline maps these to phi_scrub_audit.outcome
# / preview_status (FR-DEFACE-8).
QUARANTINE_INPUT = "quarantine_input"
QUARANTINE_RUNTIME = "quarantine_runtime"


@dataclass
class DefaceFrame:
    """A single axial JPG returned by the sidecar."""

    frame_idx: int
    jpeg_bytes: bytes


@dataclass
class DefaceSuccess:
    """200 OK from the sidecar — defaced NIfTI + per-frame JPGs."""

    frames: list[DefaceFrame]
    afni_version: str | None
    sidecar_image_tag: str | None
    duration_ms: int | None
    warning: str | None


@dataclass
class DefaceFailure:
    """4xx/5xx from the sidecar (or transport-level failure).

    ``quarantine_reason`` is one of ``QUARANTINE_INPUT`` (4xx, do NOT
    retry) or ``QUARANTINE_RUNTIME`` (5xx/timeout/transport, retry once
    per FR-DEFACE-8).
    """

    quarantine_reason: str
    error_code: str
    detail: str
    http_status: int | None


class DefaceClient:
    """Minimal HTTP client. Uses ``httpx`` if available, falls back to
    stdlib ``urllib`` so the gateway image doesn't grow a hard dep just
    for this single call."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        default_timeout_s: int = 600,
    ) -> None:
        self._base_url = (
            base_url
            or os.environ.get("DEFACE_SIDECAR_URL")
            or "http://deface-sidecar:8090"
        ).rstrip("/")
        self._default_timeout = default_timeout_s

    @property
    def base_url(self) -> str:
        return self._base_url

    def healthz(self) -> bool:
        """Cheap GET /healthz used by the pipeline to short-circuit
        deface-required series when the sidecar is down (FR-DEFACE-8)."""
        try:
            status, body, _ct = self._http_get(
                self._base_url + "/healthz", timeout_s=5
            )
            return status == 200 and b"\"ok\"" in body
        except Exception:
            return False

    # ------------------------------------------------------------------
    # /deface
    # ------------------------------------------------------------------

    def deface_series(
        self,
        *,
        dicom_dir: Path,
        timeout_s: int | None = None,
    ) -> DefaceSuccess | DefaceFailure:
        timeout = timeout_s or self._default_timeout
        try:
            tar_bytes = _tar_dicom_dir(dicom_dir)
        except OSError as exc:
            return DefaceFailure(
                quarantine_reason=QUARANTINE_INPUT,
                error_code="tar_pack_failed",
                detail=str(exc)[:255],
                http_status=None,
            )

        try:
            status, content_type, body = self._post_multipart(
                self._base_url + "/deface",
                fields=[
                    ("mode", "deface"),
                    ("timeout_s", str(timeout)),
                ],
                files=[("dicom_tar", "series.tar", "application/x-tar", tar_bytes)],
                timeout_s=timeout + 30,
            )
        except _Timeout:
            return DefaceFailure(
                quarantine_reason=QUARANTINE_RUNTIME,
                error_code="AFNI_TIMEOUT",
                detail=f"client-side timeout {timeout}s",
                http_status=504,
            )
        except _TransportError as exc:
            return DefaceFailure(
                quarantine_reason=QUARANTINE_RUNTIME,
                error_code="SIDECAR_UNREACHABLE",
                detail=str(exc)[:255],
                http_status=None,
            )

        if status == 200:
            return _parse_success(body, content_type)
        return _parse_failure(status, body, content_type)

    # ------------------------------------------------------------------
    # HTTP transport — httpx-or-urllib
    # ------------------------------------------------------------------

    def _http_get(
        self, url: str, *, timeout_s: int
    ) -> tuple[int, bytes, str | None]:
        try:
            import httpx  # type: ignore[import-not-found]

            with httpx.Client(timeout=timeout_s) as cli:
                r = cli.get(url)
                return r.status_code, r.content, r.headers.get("content-type")
        except ImportError:
            import urllib.error
            import urllib.request

            try:
                with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                    return (
                        resp.status,
                        resp.read(),
                        resp.headers.get_content_type(),
                    )
            except urllib.error.HTTPError as exc:  # pragma: no cover
                return exc.code, exc.read(), exc.headers.get_content_type()

    def _post_multipart(
        self,
        url: str,
        *,
        fields: list[tuple[str, str]],
        files: list[tuple[str, str, str, bytes]],
        timeout_s: int,
    ) -> tuple[int, str, bytes]:
        try:
            import httpx  # type: ignore[import-not-found]

            data = {k: v for k, v in fields}
            file_payload = {
                name: (filename, body, ctype) for name, filename, ctype, body in files
            }
            try:
                with httpx.Client(timeout=timeout_s) as cli:
                    r = cli.post(url, data=data, files=file_payload)
            except httpx.TimeoutException as exc:  # type: ignore[attr-defined]
                raise _Timeout(str(exc)) from exc
            except httpx.TransportError as exc:  # type: ignore[attr-defined]
                raise _TransportError(str(exc)) from exc
            return (
                r.status_code,
                r.headers.get("content-type", ""),
                r.content,
            )
        except ImportError:
            return _post_multipart_urllib(url, fields, files, timeout_s)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _Timeout(Exception):
    pass


class _TransportError(Exception):
    pass


def _tar_dicom_dir(dicom_dir: Path) -> bytes:
    """Pack every regular file under ``dicom_dir`` into a non-compressed
    tar (sidecar handles decompression). Skips empty directories."""
    if not dicom_dir.exists() or not dicom_dir.is_dir():
        raise OSError(f"dicom_dir does not exist: {dicom_dir}")
    buf = io.BytesIO()
    n = 0
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for path in sorted(dicom_dir.rglob("*")):
            if not path.is_file():
                continue
            arcname = str(path.relative_to(dicom_dir))
            tf.add(path, arcname=arcname, recursive=False)
            n += 1
    if n == 0:
        raise OSError(f"no files found under {dicom_dir}")
    return buf.getvalue()


def _parse_success(body: bytes, content_type: str | None) -> DefaceSuccess:
    """Parse the multipart response from the sidecar /deface 200 path."""
    boundary = _extract_boundary(content_type)
    parts = _split_multipart(body, boundary)
    jpgs: list[DefaceFrame] = []
    afni_version: str | None = None
    duration_ms: int | None = None
    warning: str | None = None
    for part in parts:
        name = part.name
        if name == "axial_jpgs.tar":
            jpgs = _frames_from_tar(part.body)
        elif name == "report.json":
            try:
                import json

                report = json.loads(part.body.decode("utf-8"))
            except Exception:  # pragma: no cover - report.json is optional
                report = {}
            afni_version = report.get("afni_version")
            duration_ms = report.get("duration_ms")
            warning = report.get("warning")
    return DefaceSuccess(
        frames=jpgs,
        afni_version=afni_version,
        sidecar_image_tag=os.environ.get("DEFACE_SIDECAR_IMAGE_TAG"),
        duration_ms=duration_ms,
        warning=warning,
    )


def _parse_failure(
    status: int, body: bytes, content_type: str | None
) -> DefaceFailure:
    error_code = "unknown"
    detail = ""
    try:
        import json

        envelope = json.loads(body.decode("utf-8"))
    except Exception:
        envelope = {}
    if isinstance(envelope, dict):
        error_code = str(envelope.get("error_code") or error_code)[:40]
        detail = str(envelope.get("detail") or "")[:255]
    if 400 <= status < 500:
        reason = QUARANTINE_INPUT
    else:
        reason = QUARANTINE_RUNTIME
    log.warning(
        "deface_client_failure",
        extra={
            "event": "preview.deface.fail",
            "http_status": status,
            "error_code": error_code,
            "quarantine_reason": reason,
        },
    )
    return DefaceFailure(
        quarantine_reason=reason,
        error_code=error_code or "unknown",
        detail=detail,
        http_status=status,
    )


def _extract_boundary(content_type: str | None) -> str:
    if not content_type:
        return "rv-deface-1d4f0c9c"
    for token in content_type.split(";"):
        token = token.strip()
        if token.startswith("boundary="):
            b = token.split("=", 1)[1].strip()
            return b.strip('"')
    return "rv-deface-1d4f0c9c"


@dataclass
class _MultipartPart:
    name: str
    body: bytes


def _split_multipart(body: bytes, boundary: str) -> list[_MultipartPart]:
    """Best-effort multipart splitter using stdlib email parser."""
    headers = (
        f'Content-Type: multipart/form-data; boundary="{boundary}"\r\n\r\n'
    ).encode()
    msg = BytesParser(policy=email_default_policy).parsebytes(headers + body)
    out: list[_MultipartPart] = []
    if not msg.is_multipart():
        return out
    for part in msg.iter_parts():
        cd = part.get("Content-Disposition", "")
        name = ""
        for tok in cd.split(";"):
            tok = tok.strip()
            if tok.startswith("name="):
                name = tok.split("=", 1)[1].strip().strip('"')
        payload = part.get_payload(decode=True) or b""
        out.append(_MultipartPart(name=name, body=payload))
    return out


def _frames_from_tar(tar_bytes: bytes) -> list[DefaceFrame]:
    out: list[DefaceFrame] = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
        for member in sorted(tf.getmembers(), key=lambda m: m.name):
            if not member.isfile():
                continue
            try:
                idx_str = Path(member.name).stem
                idx = int(idx_str)
            except ValueError:
                continue
            f = tf.extractfile(member)
            if f is None:
                continue
            out.append(DefaceFrame(frame_idx=idx, jpeg_bytes=f.read()))
    return out


def _post_multipart_urllib(
    url: str,
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, str, bytes]],
    timeout_s: int,
) -> tuple[int, str, bytes]:
    """urllib fallback if httpx is not installed."""
    import urllib.error
    import urllib.request
    import uuid

    boundary = f"rv-cli-{uuid.uuid4().hex[:12]}"
    parts: list[bytes] = []
    for k, v in fields:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        )
    for name, filename, ctype, body in files:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'
            ).encode()
        )
        parts.append(body)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    payload = b"".join(parts)

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header(
        "Content-Type", f"multipart/form-data; boundary={boundary}"
    )
    req.add_header("Content-Length", str(len(payload)))
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return (
                resp.status,
                resp.headers.get_content_type()
                + (
                    f"; boundary={resp.headers.get_param('boundary') or ''}"
                    if resp.headers.get_param("boundary")
                    else ""
                ),
                resp.read(),
            )
    except urllib.error.HTTPError as exc:
        ct = exc.headers.get_content_type() if exc.headers else ""
        return exc.code, ct, exc.read()
    except (TimeoutError, OSError) as exc:
        if "timed out" in str(exc).lower():
            raise _Timeout(str(exc)) from exc
        raise _TransportError(str(exc)) from exc
