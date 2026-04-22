"""boto3 S3/MinIO object store implementation (dev-spec FR-46..FR-49).

Encryption & transport guards
-----------------------------
- SSE-KMS is applied on every ``put_object`` when ``kms_key_arn`` is set.
  At construction time we reject a missing KMS key unless the operator
  explicitly opts in via ``allow_unencrypted=True`` (dev/test only), in
  which case a clear WARN log is emitted. This implements dev-spec FR-7
  (server-side encryption default) as code, not just policy.
- ``endpoint_url`` is required to be ``https://`` unless
  ``allow_insecure=True`` is set (dev/test). A WARN is logged when the
  override is enabled, so insecure transport never hides silently.
"""

from __future__ import annotations

import logging
import time
from io import BytesIO
from urllib.parse import urlsplit

from radivault_central.storage.base import ObjectStoreError
from radivault_central.telemetry import STORAGE_DURATION, STORAGE_OPERATIONS

log = logging.getLogger("radivault_central.storage.s3")


class S3ObjectStore:
    """boto3-backed S3/MinIO client with tight retry + SSE-KMS defaults."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
        force_path_style: bool = False,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        kms_key_arn: str | None = None,
        max_retries: int = 3,
        allow_unencrypted: bool = False,
        allow_insecure: bool = False,
    ) -> None:
        import boto3
        from botocore.config import Config

        # --- Encryption guard (dev-spec FR-7) -----------------------------
        if not kms_key_arn:
            if not allow_unencrypted:
                raise ObjectStoreError(
                    "S3 driver refusing to start without SSE-KMS: "
                    "storage.kms_key_arn is empty. Set storage.kms_key_arn "
                    "or pass allow_unencrypted=true explicitly (dev/test only)."
                )
            log.warning(
                "s3_unencrypted_enabled",
                extra={
                    "event": "storage.unencrypted_allowed",
                    "bucket": bucket,
                    "detail": ("S3 driver running WITHOUT SSE-KMS — not for production"),
                },
            )

        # --- Transport guard (TLS 1.3 / https-only) -----------------------
        if endpoint_url:
            scheme = urlsplit(endpoint_url).scheme.lower()
            if scheme == "http":
                if not allow_insecure:
                    raise ObjectStoreError(
                        "S3 driver refusing http:// endpoint: "
                        f"endpoint_url={endpoint_url!r}. Use https:// or "
                        "pass allow_insecure=true explicitly (dev/test only)."
                    )
                log.warning(
                    "s3_insecure_endpoint_enabled",
                    extra={
                        "event": "storage.insecure_endpoint_allowed",
                        "endpoint_url": endpoint_url,
                        "detail": (
                            "S3 driver running against http:// endpoint — not for production"
                        ),
                    },
                )
            elif scheme != "https":
                raise ObjectStoreError(
                    f"S3 driver rejects endpoint scheme {scheme!r}: {endpoint_url!r}"
                )

        self._bucket = bucket
        self._kms_key_arn = kms_key_arn
        self._max_retries = max_retries
        self._allow_unencrypted = allow_unencrypted
        self._allow_insecure = allow_insecure
        cfg = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if force_path_style else "auto"},
            retries={"max_attempts": max_retries + 1, "mode": "adaptive"},
        )
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=cfg,
        )

    # --- API ----------------------------------------------------------------

    def put_object(self, key: str, data: bytes, *, content_type: str = "application/dicom") -> None:
        started = time.time()
        attempt = 0
        delay = 0.5
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            attempt += 1
            try:
                extra: dict = {"ContentType": content_type}
                if self._kms_key_arn:
                    extra["ServerSideEncryption"] = "aws:kms"
                    extra["SSEKMSKeyId"] = self._kms_key_arn
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=BytesIO(data),
                    **extra,
                )
                STORAGE_OPERATIONS.labels(operation="put", outcome="ok").inc()
                STORAGE_DURATION.labels(operation="put").observe(time.time() - started)
                return
            except Exception as exc:
                last_exc = exc
                STORAGE_OPERATIONS.labels(operation="put", outcome="retry").inc()
                time.sleep(delay)
                delay *= 2
        STORAGE_OPERATIONS.labels(operation="put", outcome="fail").inc()
        STORAGE_DURATION.labels(operation="put").observe(time.time() - started)
        log.error(
            "s3_put_failed",
            extra={"event": "storage.write_failed", "bucket": self._bucket},
        )
        raise ObjectStoreError(f"S3 PUT retries exhausted: {last_exc}")

    def delete_objects(self, keys: list[str]) -> None:
        if not keys:
            return
        try:
            self._client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": k} for k in keys]},
            )
            STORAGE_OPERATIONS.labels(operation="delete", outcome="ok").inc()
        except Exception as exc:
            STORAGE_OPERATIONS.labels(operation="delete", outcome="fail").inc()
            log.warning(
                "s3_delete_failed",
                extra={"event": "storage.delete_failed", "detail": str(exc)},
            )

    def head_bucket(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            STORAGE_OPERATIONS.labels(operation="head", outcome="ok").inc()
            return True
        except Exception:
            STORAGE_OPERATIONS.labels(operation="head", outcome="fail").inc()
            return False
