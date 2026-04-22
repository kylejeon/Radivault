"""DICOMweb (QIDO-RS + WADO-RS) client.

Implements FR-1..FR-5. httpx-based; sync API (the v0.1 orchestrator is
single-threaded per study, so we keep the API simple for testability).

WADO-RS payloads arrive as multipart/related; we parse them into individual
Part 10 DICOM byte blobs and write one file per instance into the target
directory.
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import httpx


log = logging.getLogger("radivault.pacs")


class PacsError(Exception):
    """Raised on unrecoverable PACS client errors."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class StudySummary:
    study_instance_uid: str
    patient_id: str
    study_date: str
    modalities_in_study: list[str]
    num_instances: int | None = None


@dataclass
class FetchResult:
    study_instance_uid: str
    instance_paths: list[Path] = field(default_factory=list)
    bytes_total: int = 0
    duration_ms: int = 0


def _qido_value(item: dict[str, Any], tag: str, vr: str = "Value") -> Any:
    block = item.get(tag)
    if not block:
        return None
    values = block.get(vr)
    if not values:
        return None
    first = values[0]
    if isinstance(first, dict):
        # PN format: {"Alphabetic": "..."}
        return first.get("Alphabetic") or next(iter(first.values()), None)
    return first


class DicomWebPacsClient:
    """Synchronous QIDO/WADO-RS client.

    Parameters are aligned with dev-spec §7.1. Authentication supports Bearer
    and Basic; TLS verification defaults to on; self-signed CAs may be trusted
    via the ``ca_bundle`` parameter (path).
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_type: str = "bearer",
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        ca_bundle: str | Path | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 5,
        retry_initial: float = 1.0,
        retry_factor: float = 2.0,
        retry_jitter: float = 0.2,
        retry_cap: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Accept": "application/dicom+json"}
        auth: Any = None
        if auth_type == "bearer":
            if not token:
                raise ValueError("bearer auth requires a token")
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "basic":
            if not username or not password:
                raise ValueError("basic auth requires username + password")
            auth = httpx.BasicAuth(username, password)
        else:
            raise ValueError(f"unsupported auth type: {auth_type}")

        verify: Any = True
        if ca_bundle:
            verify = str(ca_bundle)
        self._client = httpx.Client(
            headers=headers,
            auth=auth,
            verify=verify,
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self._max_retries = max_retries
        self._retry_initial = retry_initial
        self._retry_factor = retry_factor
        self._retry_jitter = retry_jitter
        self._retry_cap = retry_cap

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DicomWebPacsClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---- retry helper ----

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        delay = self._retry_initial
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._client.request(method, url, params=params, headers=headers)
                if resp.status_code < 500:
                    return resp
                last_exc = PacsError(
                    f"server error {resp.status_code}", status_code=resp.status_code
                )
            except httpx.HTTPError as exc:
                last_exc = exc
            if attempt >= self._max_retries:
                break
            jitter = 1.0 + random.uniform(-self._retry_jitter, self._retry_jitter)
            sleep_for = min(delay * jitter, self._retry_cap)
            log.warning(
                "pacs request failed, retry",
                extra={"attempt": attempt, "delay_s": round(sleep_for, 2)},
            )
            time.sleep(sleep_for)
            delay *= self._retry_factor
        if isinstance(last_exc, PacsError):
            raise last_exc
        raise PacsError(f"PACS request failed after retries: {last_exc}")

    # ---- QIDO ----

    def query_studies(
        self,
        study_date_from: date,
        study_date_to: date,
        modalities: Iterable[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StudySummary]:
        params: dict[str, Any] = {
            "StudyDate": f"{study_date_from.strftime('%Y%m%d')}-{study_date_to.strftime('%Y%m%d')}",
            "limit": limit,
            "offset": offset,
        }
        if modalities:
            params["ModalitiesInStudy"] = ",".join(modalities)
        url = f"{self.base_url}/studies"
        resp = self._request_with_retry("GET", url, params=params)
        if resp.status_code == 204 or not resp.content:
            return []
        if resp.status_code >= 400:
            raise PacsError(
                f"QIDO error {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        items = resp.json() if resp.content else []
        result: list[StudySummary] = []
        for item in items:
            study_uid = _qido_value(item, "0020000D")
            if not study_uid:
                continue
            modalities_val = item.get("00080061", {}).get("Value", []) or []
            result.append(
                StudySummary(
                    study_instance_uid=str(study_uid),
                    patient_id=str(_qido_value(item, "00100020") or ""),
                    study_date=str(_qido_value(item, "00080020") or ""),
                    modalities_in_study=[str(m) for m in modalities_val],
                    num_instances=_qido_value(item, "00201208"),
                )
            )
        return result

    # ---- WADO-RS ----

    def fetch_study(self, study_instance_uid: str, out_dir: Path) -> FetchResult:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/studies/{study_instance_uid}"
        headers = {"Accept": "multipart/related; type=application/dicom"}
        started = time.time()
        resp = self._request_with_retry("GET", url, headers=headers)
        if resp.status_code >= 400:
            raise PacsError(
                f"WADO error {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        content_type = resp.headers.get("content-type", "")
        parts = _split_multipart(resp.content, content_type)
        paths: list[Path] = []
        total_bytes = 0
        for idx, part in enumerate(parts):
            path = out_dir / f"{idx:05d}.dcm"
            path.write_bytes(part)
            paths.append(path)
            total_bytes += len(part)
        duration_ms = int((time.time() - started) * 1000)
        return FetchResult(
            study_instance_uid=study_instance_uid,
            instance_paths=paths,
            bytes_total=total_bytes,
            duration_ms=duration_ms,
        )

    def health_check(self) -> bool:
        try:
            resp = self._client.get(f"{self.base_url}/studies", params={"limit": 1})
        except httpx.HTTPError:
            return False
        return resp.status_code < 500


_BOUNDARY_RE = re.compile(r'boundary=(?:"([^"]+)"|([^;\s]+))', re.IGNORECASE)


def _split_multipart(body: bytes, content_type: str) -> list[bytes]:
    """Parse a multipart/related response body into raw DICOM byte parts.

    DICOMweb servers emit ``multipart/related; type="application/dicom";
    boundary=...`` — we need the boundary and the bytes between separators.
    Only strict ``\r\n\r\n`` header/body separators are supported (the DICOMweb
    reference implementations comply).
    """
    match = _BOUNDARY_RE.search(content_type or "")
    if not match:
        # Fall back: single-part body (e.g. test doubles that return raw DICOM)
        return [body] if body else []
    boundary = (match.group(1) or match.group(2)).encode("ascii")
    sep = b"--" + boundary
    closing = sep + b"--"
    parts: list[bytes] = []
    for chunk in body.split(sep):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk.startswith(b"--"):
            continue
        header_end = chunk.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        payload = chunk[header_end + 4 :]
        # strip trailing CRLF before next boundary
        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        if payload:
            parts.append(payload)
    # Tolerate the closing boundary
    _ = closing
    return parts
