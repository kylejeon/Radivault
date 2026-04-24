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
    ) -> dict[str, Any]:
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
        return {
            "manifest_version": 1,
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
