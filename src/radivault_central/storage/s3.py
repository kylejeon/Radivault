"""boto3 S3/MinIO object store implementation (dev-spec FR-46..FR-49)."""

from __future__ import annotations

import logging
import time
from io import BytesIO

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
    ) -> None:
        import boto3
        from botocore.config import Config

        self._bucket = bucket
        self._kms_key_arn = kms_key_arn
        self._max_retries = max_retries
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

    def put_object(
        self, key: str, data: bytes, *, content_type: str = "application/dicom"
    ) -> None:
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
        log.error("s3_put_failed", extra={"event": "storage.write_failed", "bucket": self._bucket})
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
            log.warning("s3_delete_failed", extra={"event": "storage.delete_failed", "detail": str(exc)})

    def head_bucket(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            STORAGE_OPERATIONS.labels(operation="head", outcome="ok").inc()
            return True
        except Exception:
            STORAGE_OPERATIONS.labels(operation="head", outcome="fail").inc()
            return False
