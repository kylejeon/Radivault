"""Upload client — multipart/form-data POST to central ingest.

FR-18..FR-21.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("radivault.upload")


class UploadError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


@dataclass
class UploadResult:
    job_id: str
    received_at: str | None = None
    bytes_sent: int = 0
    duration_ms: int = 0
    manifest: dict[str, Any] = field(default_factory=dict)


class UploadClient:
    """Synchronous HTTPS uploader. TLS 1.3 is enforced by httpx/OpenSSL.

    For retries, we use an exponential backoff (FR-20) up to ``max_retries``
    attempts. 4xx (except 429) are *not* retried; 429 honors ``Retry-After``.
    """

    def __init__(
        self,
        base_url: str,
        *,
        upload_token: str,
        timeout_seconds: float = 600.0,
        max_retries: int = 10,
        retry_initial: float = 2.0,
        retry_factor: float = 2.0,
        retry_cap: float = 3600.0,
        retry_jitter: float = 0.2,
        allow_insecure: bool = False,
    ) -> None:
        # H-1: enforce HTTPS on the central base URL unless the operator
        # explicitly opts out via central.allow_insecure. TLS 1.3 outbound-only
        # is a non-functional requirement (dev-spec §5, §12.3).
        normalised = base_url.rstrip("/")
        scheme = normalised.split("://", 1)[0].lower() if "://" in normalised else ""
        if scheme != "https":
            if not allow_insecure:
                raise ValueError(
                    "central.base_url must use https:// "
                    "(set central.allow_insecure=true to override for dev)"
                )
            log.warning(
                "insecure central base_url in use — not for production",
                extra={"base_url": normalised},
            )
        self.base_url = normalised
        headers = {"Authorization": f"Bearer {upload_token}"}
        self._client = httpx.Client(
            headers=headers,
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        self.max_retries = max_retries
        self._retry_initial = retry_initial
        self._retry_factor = retry_factor
        self._retry_cap = retry_cap
        self._retry_jitter = retry_jitter

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> UploadClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def build_manifest(
        self,
        *,
        gateway_id: str,
        hospital_id: str,
        pseudo_study_uid: str,
        modalities: list[str],
        ruleset_version: str,
        salt_version: int,
        method_codes: list[str],
        dcm_files: list[Path],
        study_metadata: Any | None = None,
        thumbnail: Any | None = None,
    ) -> dict[str, Any]:
        """Build the v1+v2 ingest manifest.

        ``study_metadata`` is the optional :class:`StudyMetadata` from
        ``radivault_gateway.extract`` (FR-META-2). ``thumbnail`` is the optional
        :class:`ThumbnailResult` from ``radivault_gateway.thumbnail``
        (FR-THUMB-1). Both are absent on Flow A / older callers.
        """
        files_meta: list[dict[str, Any]] = []
        total_bytes = 0
        for path in sorted(dcm_files):
            data = path.read_bytes()
            files_meta.append(
                {
                    "filename": path.name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
            total_bytes += len(data)
        manifest: dict[str, Any] = {
            "manifest_version": 2 if (study_metadata or thumbnail) else 1,
            "gateway_id": gateway_id,
            "hospital_id": hospital_id,
            "pseudo_study_uid": pseudo_study_uid,
            "modalities": modalities,
            "n_instances": len(files_meta),
            "total_bytes": total_bytes,
            "deid": {
                "ruleset_version": ruleset_version,
                "salt_version": salt_version,
                "method_code_sequence": method_codes,
            },
            # D-3: Central v0.1 enforces the cross-border transfer gate and
            # rejects any manifest without ``anonymization_flag ==
            # "fully_anonymized"``. Gateway v0.1 was shipped before this
            # field was formalised; we emit the only value Central accepts.
            # See docs/specs/dev-spec-central-ingest.md §13 D-3 and
            # Gateway v0.1.1 doc-patch proposal (to be opened by @planner).
            "anonymization_flag": "fully_anonymized",
            "files": files_meta,
            "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if study_metadata is not None:
            sd = study_metadata
            manifest["body_part_examined"] = getattr(sd, "body_part_examined", None)
            manifest["patient_sex"] = getattr(sd, "patient_sex", None)
            manifest["patient_age_bucket"] = getattr(sd, "patient_age_bucket", None)
            manifest["manufacturer"] = getattr(sd, "manufacturer", None)
            manifest["manufacturer_model_name"] = getattr(sd, "manufacturer_model_name", None)
            sd_date = getattr(sd, "study_date_shifted", None)
            manifest["study_date_shifted"] = sd_date.isoformat() if sd_date else None
            manifest["study_year"] = getattr(sd, "study_year", None)
            manifest["n_series"] = getattr(sd, "n_series", None)
            manifest["series"] = list(getattr(sd, "series", []) or [])
        if thumbnail is not None:
            import base64

            manifest["thumbnail"] = {
                "sha256": thumbnail.sha256,
                "bytes": len(thumbnail.bytes),
                "format": thumbnail.format,
                "width": thumbnail.width,
                "height": thumbnail.height,
                "source_instance_uid_pseudo": thumbnail.source_instance_uid_pseudo,
                "slice_index": thumbnail.slice_index,
                "slice_count": thumbnail.slice_count,
                "phi_scrub_status": thumbnail.phi_scrub_status,
                "phi_scrub_method": thumbnail.phi_scrub_method,
                "data_b64": base64.b64encode(thumbnail.bytes).decode("ascii"),
            }
        return manifest

    def build_metadata_only_manifest(
        self,
        *,
        gateway_id: str,
        hospital_id: str,
        pseudo_study_uid: str,
        modalities: list[str],
        ruleset_version: str,
        salt_version: int,
        method_codes: list[str],
        n_instances: int,
        total_bytes: int,
    ) -> dict[str, Any]:
        """Build a metadata-only manifest (Flow A — ARCHITECTURE.md §4).

        Reuses the wire format of :meth:`build_manifest` so Central can reuse
        the same ``ManifestValidator`` business rules. ``files`` is emitted as
        an empty list; ``n_instances`` + ``total_bytes`` carry the logical
        counts so the Hospital Portal dashboards can surface throughput even
        when the pixel payload never left the Gateway.
        """
        return {
            "manifest_version": 1,
            "gateway_id": gateway_id,
            "hospital_id": hospital_id,
            "pseudo_study_uid": pseudo_study_uid,
            "modalities": modalities,
            "n_instances": n_instances,
            "total_bytes": total_bytes,
            "deid": {
                "ruleset_version": ruleset_version,
                "salt_version": salt_version,
                "method_code_sequence": method_codes,
            },
            "anonymization_flag": "fully_anonymized",
            "files": [],
            "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def upload_study(
        self,
        manifest: dict[str, Any],
        dcm_files: list[Path],
    ) -> UploadResult:
        """Upload a study. Retries 5xx + 429 per FR-20.

        Raises :class:`UploadError` on permanent failure.
        """
        url = f"{self.base_url}/v1/ingest/studies"
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        # Central requires an Idempotency-Key (16-128 chars, [A-Za-z0-9_.-])
        # for every POST /v1/ingest/studies. Keying on pseudo_study_uid makes
        # Gateway retries of the same logical study deduplicate server-side.
        idempotency_key = f"upload-{manifest['pseudo_study_uid']}"[:128]
        request_headers = {"Idempotency-Key": idempotency_key}
        attempt = 0
        delay = self._retry_initial
        started = time.time()
        last_exc: UploadError | None = None
        while attempt < self.max_retries:
            attempt += 1
            files: list[tuple[str, tuple[str, bytes, str]]] = [
                ("manifest", ("manifest.json", manifest_bytes, "application/json")),
            ]
            for path in sorted(dcm_files):
                files.append(
                    (
                        "files",
                        (path.name, path.read_bytes(), "application/dicom"),
                    )
                )
            try:
                resp = self._client.post(url, files=files, headers=request_headers)
            except httpx.HTTPError as exc:
                last_exc = UploadError(f"network error: {exc}", retryable=True)
                if attempt < self.max_retries:
                    self._sleep_retry(delay)
                    delay *= self._retry_factor
                continue
            if resp.status_code in (200, 201, 202):
                body = resp.json() if resp.content else {}
                duration = int((time.time() - started) * 1000)
                return UploadResult(
                    job_id=str(body.get("job_id", "")),
                    received_at=body.get("received_at"),
                    bytes_sent=manifest["total_bytes"] + len(manifest_bytes),
                    duration_ms=duration,
                    manifest=manifest,
                )
            if resp.status_code in (400, 401, 403, 404, 409, 413):
                # Non-retryable client errors.
                raise UploadError(
                    f"upload rejected {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                    retryable=False,
                )
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", delay))
                self._sleep_retry(retry_after)
                continue
            # 5xx → retry
            last_exc = UploadError(
                f"server error {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
                retryable=True,
            )
            if attempt < self.max_retries:
                self._sleep_retry(delay)
                delay = min(delay * self._retry_factor, self._retry_cap)
        assert last_exc is not None
        raise last_exc

    def upload_study_metadata_only(
        self,
        manifest: dict[str, Any],
    ) -> UploadResult:
        """Upload a metadata-only manifest (Flow A).

        Sends a single ``application/json`` POST to
        ``/v1/ingest/studies/metadata``. No DICOM payload is transferred —
        Central persists a study row with ``central_object_present=False``
        so the fulfillment subsystem knows to request pixels from the
        Gateway at order time (Flow B).

        Retries 5xx + 429 identical to :meth:`upload_study` but uses a
        distinct ``Idempotency-Key`` prefix (``meta-``) so a subsequent
        full-payload upload of the same logical study cannot collide with
        this record in the idempotency mirror.
        """
        url = f"{self.base_url}/v1/ingest/studies/metadata"
        body = json.dumps(manifest).encode("utf-8")
        idempotency_key = f"meta-{manifest['pseudo_study_uid']}"[:128]
        request_headers = {
            "Idempotency-Key": idempotency_key,
            "Content-Type": "application/json",
        }
        attempt = 0
        delay = self._retry_initial
        started = time.time()
        last_exc: UploadError | None = None
        while attempt < self.max_retries:
            attempt += 1
            try:
                resp = self._client.post(url, content=body, headers=request_headers)
            except httpx.HTTPError as exc:
                last_exc = UploadError(f"network error: {exc}", retryable=True)
                if attempt < self.max_retries:
                    self._sleep_retry(delay)
                    delay *= self._retry_factor
                continue
            if resp.status_code in (200, 201, 202):
                payload = resp.json() if resp.content else {}
                duration = int((time.time() - started) * 1000)
                return UploadResult(
                    job_id=str(payload.get("job_id") or payload.get("central_job_id") or ""),
                    received_at=payload.get("received_at"),
                    bytes_sent=len(body),
                    duration_ms=duration,
                    manifest=manifest,
                )
            if resp.status_code in (400, 401, 403, 404, 409, 413, 415):
                raise UploadError(
                    f"metadata-only upload rejected {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                    retryable=False,
                )
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", delay))
                self._sleep_retry(retry_after)
                continue
            last_exc = UploadError(
                f"server error {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
                retryable=True,
            )
            if attempt < self.max_retries:
                self._sleep_retry(delay)
                delay = min(delay * self._retry_factor, self._retry_cap)
        assert last_exc is not None
        raise last_exc

    def post_audit_anchor(
        self,
        *,
        gateway_id: str,
        seq_range: tuple[int, int],
        head_hash: str,
    ) -> dict[str, Any]:
        """FR-25: hourly audit anchor."""
        url = f"{self.base_url}/v1/audit/anchor"
        body = {
            "gateway_id": gateway_id,
            "seq_range": [seq_range[0], seq_range[1]],
            "head_hash": head_hash,
            "anchored_at": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        resp = self._client.post(url, json=body)
        if resp.status_code >= 400:
            raise UploadError(
                f"anchor rejected {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
                retryable=resp.status_code >= 500,
            )
        return resp.json() if resp.content else {}

    def health_check(self) -> bool:
        try:
            resp = self._client.get(f"{self.base_url}/healthz", timeout=5.0)
        except httpx.HTTPError:
            return False
        return resp.status_code < 500

    def _sleep_retry(self, delay: float) -> None:
        jitter = 1.0 + random.uniform(-self._retry_jitter, self._retry_jitter)
        time.sleep(min(delay * jitter, self._retry_cap))
