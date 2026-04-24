"""DICOMweb (QIDO-RS + WADO-RS) client.

Implements FR-1..FR-5. httpx-based; sync API (the v0.1 orchestrator is
single-threaded per study, so we keep the API simple for testability).

WADO-RS payloads arrive as multipart/related; we parse them into individual
Part 10 DICOM byte blobs and write one file per instance into the target
directory.

QIDO pagination: :meth:`DicomWebPacsClient.query_studies` is internally
paged (default page size = 500 rows) and transparently returns the full
result set to callers. Orthanc and DCM4CHE both cap a single QIDO response
at a small default (Orthanc = 100 unless the client overrides ``limit``);
callers never see page boundaries.
"""

from __future__ import annotations

import logging
import random
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from radivault_gateway.pacs.dicom_json import (
    json_to_datasets,
    write_datasets_to_dir,
)

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


@dataclass(frozen=True)
class StudyQidoSummary:
    """Study-level counters extracted from a QIDO-RS ``/studies`` response.

    Powers the Flow A (metadata-only) fast-path (gateway-flow-a-qido). QIDO
    returns a one-row-per-study JSON payload that carries every field the
    metadata-only manifest needs (``ModalitiesInStudy``,
    ``NumberOfStudyRelatedInstances``) — replacing the per-instance
    ``/studies/{uid}/metadata`` pull which on Orthanc is ~56x slower.
    """

    study_instance_uid: str
    modalities: list[str]
    n_instances: int
    n_series: int
    study_date: str | None = None
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

    def __enter__(self) -> DicomWebPacsClient:
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

    # Max QIDO pages we will ever walk in a single ``query_studies`` call.
    # 200 pages * default page size 500 = 100,000 studies. Production Korean
    # hospitals emit << 10k studies/day; this cap is a cheap infinite-loop
    # guard against a broken PACS that keeps echoing full pages.
    _QIDO_MAX_PAGES = 200

    def query_studies(
        self,
        study_date_from: date,
        study_date_to: date,
        modalities: Iterable[str] | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[StudySummary]:
        """Return every QIDO ``/studies`` row matching the date window.

        ``limit`` and ``offset`` are **internal pagination** knobs, not a
        user-facing result cap: ``limit`` sets the page size per QIDO
        request (default 500, chosen so a typical hospital day fits in a
        single round-trip) and ``offset`` is the starting cursor. The method
        walks pages — issuing ``GET /studies?...&limit=<page>&offset=<cur>``
        until the server returns fewer than ``limit`` rows (or zero), then
        returns the concatenated, UID-deduped list.

        Rationale for the bug this fixes: Orthanc caps an unbounded QIDO
        request at 100 rows. Before pagination was added the gateway silently
        processed only the first 100 studies of a 255-study source, which
        violated the sync-once "all matches in window" contract.

        Raises :class:`PacsError` on unrecoverable HTTP errors or when the
        server emits more than ``_QIDO_MAX_PAGES`` full pages (cheap
        infinite-loop guard).
        """
        url = f"{self.base_url}/studies"
        study_date_param = (
            f"{study_date_from.strftime('%Y%m%d')}-"
            f"{study_date_to.strftime('%Y%m%d')}"
        )
        base_params: dict[str, Any] = {"StudyDate": study_date_param}
        if modalities:
            base_params["ModalitiesInStudy"] = ",".join(modalities)

        page_size = limit
        cursor = offset
        pages_fetched = 0
        all_rows: list[StudySummary] = []
        started = time.time()

        while True:
            if pages_fetched >= self._QIDO_MAX_PAGES:
                raise PacsError(
                    f"QIDO pagination exceeded max_pages={self._QIDO_MAX_PAGES}"
                )
            params = {**base_params, "limit": page_size, "offset": cursor}
            resp = self._request_with_retry("GET", url, params=params)
            pages_fetched += 1

            if resp.status_code == 204 or not resp.content:
                # Empty body = end of results. Terminate.
                break
            if resp.status_code >= 400:
                raise PacsError(
                    f"QIDO error {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )
            items = resp.json() if resp.content else []
            page_len = len(items) if isinstance(items, list) else 0
            log.debug(
                "qido page",
                extra={"offset": cursor, "returned": page_len},
            )
            if not isinstance(items, list) or page_len == 0:
                break

            for item in items:
                study_uid = _qido_value(item, "0020000D")
                if not study_uid:
                    continue
                modalities_val = item.get("00080061", {}).get("Value", []) or []
                all_rows.append(
                    StudySummary(
                        study_instance_uid=str(study_uid),
                        patient_id=str(_qido_value(item, "00100020") or ""),
                        study_date=str(_qido_value(item, "00080020") or ""),
                        modalities_in_study=[str(m) for m in modalities_val],
                        num_instances=_qido_value(item, "00201208"),
                    )
                )

            # Partial page ⇒ last page reached. Avoids one extra empty
            # round-trip when the tail exactly matches the page size.
            if page_len < page_size:
                break
            cursor += page_size

        # StudyInstanceUID dedupe while preserving first-seen order. Guards
        # against duplicates that appear near page boundaries when the PACS
        # sort order is unstable (Orthanc sorts by StudyDate without a
        # stable tie-breaker).
        deduped: dict[str, StudySummary] = {}
        for row in all_rows:
            if row.study_instance_uid not in deduped:
                deduped[row.study_instance_uid] = row
        result = list(deduped.values())

        duration_ms = int((time.time() - started) * 1000)
        log.info(
            "qido pagination done",
            extra={
                "total": len(result),
                "pages": pages_fetched,
                "duration_ms": duration_ms,
            },
        )
        return result

    def fetch_study_qido_summary(self, study_instance_uid: str) -> StudyQidoSummary:
        """Pull a single-study QIDO-RS row and return the counters Flow A needs.

        Implements the gateway-flow-a-qido fast-path. Hits
        ``GET /studies?StudyInstanceUID=<uid>`` — a kilobyte-scale response —
        rather than ``/studies/{uid}/metadata`` which forces the PACS to read
        every instance from disk (on a 192-slice CT: 2.25 MB payload / ~14 s
        on Orthanc vs 1.2 KB / 0.25 s for QIDO).

        The response is the standard DICOMweb JSON VR form
        ``{"00080061": {"vr": "CS", "Value": ["CT"]}, ...}``. We defensively
        tolerate missing ``Value`` arrays (Orthanc has emitted both
        ``Value: null`` and a missing key in different builds) by falling
        back to empty / zero defaults, matching the manifest contract
        (``modalities=[]``, ``n_instances=0``).

        Raises :class:`PacsError` when the study is not present in the
        source PACS (empty array response).
        """
        url = f"{self.base_url}/studies"
        params = {"StudyInstanceUID": study_instance_uid, "limit": 1}
        started = time.time()
        resp = self._request_with_retry("GET", url, params=params)
        if resp.status_code >= 400:
            raise PacsError(
                f"QIDO study summary error {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        if resp.status_code == 204 or not resp.content:
            raise PacsError(
                f"study not found: {study_instance_uid}",
                status_code=resp.status_code,
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise PacsError(
                f"QIDO study summary: non-JSON response: {exc}",
                status_code=resp.status_code,
            ) from exc
        if not isinstance(payload, list) or not payload:
            raise PacsError(
                f"study not found: {study_instance_uid}",
                status_code=resp.status_code,
            )
        item = payload[0]
        # ModalitiesInStudy (0008,0061) is VR=CS, multi-valued. When the PACS
        # omits the block entirely (some mini DICOMweb servers do) or sets
        # ``Value`` to null, default to an empty list so the manifest stays
        # well-formed. The Hospital Portal dashboards render ``—`` for empty.
        modalities_block = item.get("00080061") or {}
        raw_modalities = modalities_block.get("Value") or []
        modalities = [str(m) for m in raw_modalities if m is not None]
        # NumberOfStudyRelatedInstances (0020,1208) — integer string per VR IS.
        n_instances_raw = _qido_value(item, "00201208")
        try:
            n_instances = int(n_instances_raw) if n_instances_raw is not None else 0
        except (TypeError, ValueError):
            n_instances = 0
        # NumberOfStudyRelatedSeries (0020,1206) — captured for audit / debug.
        n_series_raw = _qido_value(item, "00201206")
        try:
            n_series = int(n_series_raw) if n_series_raw is not None else 0
        except (TypeError, ValueError):
            n_series = 0
        study_date = _qido_value(item, "00080020")
        study_date_str = str(study_date) if study_date is not None else None
        duration_ms = int((time.time() - started) * 1000)
        return StudyQidoSummary(
            study_instance_uid=study_instance_uid,
            modalities=modalities,
            n_instances=n_instances,
            n_series=n_series,
            study_date=study_date_str,
            duration_ms=duration_ms,
        )

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

    def fetch_study_metadata(self, study_instance_uid: str, out_dir: Path) -> FetchResult:
        """Flow A (metadata-only) fetch — **DEPRECATED in the fast-path**.

        Retained for debug / legacy reproduction only. As of
        gateway-flow-a-qido the metadata-only pipeline uses
        :meth:`fetch_study_qido_summary` (a single QIDO row, ~0.25 s on
        Orthanc) instead of this per-instance WADO metadata call (~14 s on
        a 192-slice CT). No production code path invokes this method.

        Calls the DICOMweb ``/studies/{uid}/metadata`` endpoint (PS3.18 §10.4)
        with ``Accept: application/dicom+json`` and materialises one
        pixel-free Part-10 ``.dcm`` file per instance under ``out_dir``. The
        return shape matches :meth:`fetch_study` so the orchestrator can swap
        implementations without touching its downstream de-ID / staging
        bookkeeping (FR-6..FR-15 operate on filesystem inputs).

        No pixel data ever crosses the wire — the JSON payload references
        ``PixelData`` as a ``BulkDataURI`` which we drop (see
        :mod:`radivault_gateway.pacs.dicom_json`). Typical Orthanc responses
        are a few KB per instance versus several MB for a full WADO-RS
        multipart, yielding the 10-100x fetch-time win Flow A was designed
        for (ARCHITECTURE.md §4).
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/studies/{study_instance_uid}/metadata"
        headers = {"Accept": "application/dicom+json"}
        started = time.time()
        resp = self._request_with_retry("GET", url, headers=headers)
        if resp.status_code >= 400:
            raise PacsError(
                f"WADO metadata error {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        # 204 = study empty → return a zero-instance result rather than raising;
        # the orchestrator audits ``n_instances=0`` and moves on.
        if resp.status_code == 204 or not resp.content:
            duration_ms = int((time.time() - started) * 1000)
            return FetchResult(
                study_instance_uid=study_instance_uid,
                instance_paths=[],
                bytes_total=0,
                duration_ms=duration_ms,
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise PacsError(
                f"WADO metadata: non-JSON response: {exc}",
                status_code=resp.status_code,
            ) from exc
        if not isinstance(payload, list):
            raise PacsError(
                f"WADO metadata: expected JSON array, got {type(payload).__name__}",
                status_code=resp.status_code,
            )
        datasets = json_to_datasets(payload)
        paths, total_bytes = write_datasets_to_dir(datasets, out_dir)
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
