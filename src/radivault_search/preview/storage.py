"""Preview cache storage adapter — MinIO + local FS fallback.

Q-5 default: a dedicated ``radivault-preview`` MinIO bucket holds three
prefix groups:

    thumbnails/{study_uid}.jpg                  256x256 JPEG
    frames/{study_uid}/{series_num}/{n}.jpg     full-res preview frames
    samples/{study_uid}/{sop_uid}.dcm           single-instance DICOM

This module exposes one Protocol — :class:`PreviewStore` — and two
implementations:

    * :class:`S3PreviewStore` (boto3 / MinIO) — production path.
    * :class:`LocalPreviewStore` (filesystem) — pytest fixtures so unit
      tests don't need a live MinIO.

The Protocol is intentionally narrower than the central-ingest
``ObjectStore`` because preview reads dominate (the only writes happen
in the seed script, which uses boto3 directly).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Protocol
from urllib.parse import urlsplit

log = logging.getLogger("radivault_search.preview.storage")


class PreviewStorageError(RuntimeError):
    """Raised when a preview-store call fails irrecoverably."""


class PreviewObjectNotFound(PreviewStorageError):
    """Raised when a thumbnail / frame / sample object is missing."""


class PreviewStore(Protocol):
    """Narrow Protocol — only the operations the preview router needs."""

    def get_jpeg(self, key: str) -> tuple[bytes, str]:
        """Return ``(jpeg_bytes, etag)`` for an existing object."""
        ...

    def stream_jpeg(self, key: str, *, chunk_size: int = 65536) -> Iterator[bytes]:
        """Stream JPEG bytes (used by FastAPI StreamingResponse)."""
        ...

    def head(self, key: str) -> int:
        """Return content-length for an existing object (raise if missing)."""
        ...

    def presign_get(self, key: str, *, ttl_seconds: int = 3600) -> tuple[str, int]:
        """Return ``(presigned_url, size_bytes)`` for a sample DICOM."""
        ...


# ---------------------------------------------------------------------------
# S3 / MinIO implementation
# ---------------------------------------------------------------------------


class S3PreviewStore:
    """boto3-backed preview cache.

    Unlike the ingest ``S3ObjectStore`` we permit ``http://`` endpoints
    when ``allow_insecure=True`` is set (dev-only) because MinIO local
    deployments routinely run on plain HTTP behind a reverse proxy. The
    presign call uses standard SigV4; URLs are valid for ``ttl_seconds``.
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        allow_insecure: bool = False,
    ) -> None:
        import boto3
        from botocore.config import Config

        if endpoint_url:
            scheme = urlsplit(endpoint_url).scheme.lower()
            if scheme not in ("http", "https"):
                raise PreviewStorageError(
                    f"Preview store: unsupported endpoint scheme {scheme!r}"
                )
            if scheme == "http" and not allow_insecure:
                raise PreviewStorageError(
                    "Preview store refusing http:// endpoint. Set "
                    "allow_insecure=True for dev/test (MinIO local)."
                )

        self._bucket = bucket
        cfg = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=cfg,
        )

    def get_jpeg(self, key: str) -> tuple[bytes, str]:
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey as exc:
            raise PreviewObjectNotFound(key) from exc
        except Exception as exc:  # noqa: BLE001
            # ClientError 404 vs other failure — treat 404 as not-found.
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise PreviewObjectNotFound(key) from exc
            raise PreviewStorageError(f"get_object failed: {exc}") from exc
        body = obj["Body"].read()
        etag = (obj.get("ETag") or "").strip('"')
        return body, etag

    def stream_jpeg(self, key: str, *, chunk_size: int = 65536) -> Iterator[bytes]:
        body, _ = self.get_jpeg(key)
        # We pre-load + slice so ``StreamingResponse`` retains an Iterator;
        # for the 30 KB thumbnail / ~250 KB frame this is fine and matches
        # the existing local-fs adapter behaviour.
        for i in range(0, len(body), chunk_size):
            yield body[i : i + chunk_size]

    def head(self, key: str) -> int:
        try:
            obj = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404", "NotFound"):
                raise PreviewObjectNotFound(key) from exc
            raise PreviewStorageError(f"head_object failed: {exc}") from exc
        return int(obj["ContentLength"])

    def presign_get(self, key: str, *, ttl_seconds: int = 3600) -> tuple[str, int]:
        # Verify presence first so callers get a clean 404 instead of a
        # presigned URL that would 404 on dereference.
        size = self.head(key)
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise PreviewStorageError(f"presign failed: {exc}") from exc
        return url, size


# ---------------------------------------------------------------------------
# Local-FS implementation (tests + dev fallback)
# ---------------------------------------------------------------------------


class LocalPreviewStore:
    """Filesystem-backed adapter — used by pytest + local dev w/o MinIO.

    Presigned URLs are synthesised as deterministic ``http://local-preview/``
    URLs with an ``expires_at`` query param so audit log code paths see a
    real-shaped string. The URL is NOT actually dereferenceable — tests
    that need the bytes call ``get_jpeg`` directly.
    """

    def __init__(self, root: str | Path, *, base_url: str = "http://local-preview") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._base_url = base_url.rstrip("/")

    def _resolve(self, key: str) -> Path:
        # Mild traversal guard — same logic as central-ingest local store.
        if not key or "\x00" in key or "\\" in key or key.startswith("/"):
            raise PreviewStorageError(f"illegal key: {key!r}")
        if any(p == ".." for p in key.split("/")):
            raise PreviewStorageError(f"parent-segment key: {key!r}")
        return self._root / key

    def get_jpeg(self, key: str) -> tuple[bytes, str]:
        path = self._resolve(key)
        if not path.exists():
            raise PreviewObjectNotFound(key)
        body = path.read_bytes()
        # Use a synthetic ETag based on size+mtime so HTTP cache validation
        # can still tell when the file changes.
        stat = path.stat()
        etag = f"{stat.st_size:x}-{int(stat.st_mtime):x}"
        return body, etag

    def stream_jpeg(self, key: str, *, chunk_size: int = 65536) -> Iterator[bytes]:
        body, _ = self.get_jpeg(key)
        for i in range(0, len(body), chunk_size):
            yield body[i : i + chunk_size]

    def head(self, key: str) -> int:
        path = self._resolve(key)
        if not path.exists():
            raise PreviewObjectNotFound(key)
        return path.stat().st_size

    def presign_get(self, key: str, *, ttl_seconds: int = 3600) -> tuple[str, int]:
        size = self.head(key)
        expires_at = (
            datetime.now(tz=timezone.utc) + timedelta(seconds=ttl_seconds)
        ).strftime("%Y%m%dT%H%M%SZ")
        url = f"{self._base_url}/{key}?X-Amz-Expires={ttl_seconds}&X-Amz-Date={expires_at}"
        return url, size


# ---------------------------------------------------------------------------
# Key helpers — single source of truth for key shapes (FR-DATA-1 §6.5)
# ---------------------------------------------------------------------------


def thumbnail_key(study_uid: str) -> str:
    return f"thumbnails/{study_uid}.jpg"


def frame_key(study_uid: str, series_num: int, frame_num: int) -> str:
    return f"frames/{study_uid}/{series_num}/{frame_num}.jpg"


def sample_key(study_uid: str, sop_instance_uid: str) -> str:
    return f"samples/{study_uid}/{sop_instance_uid}.dcm"


__all__ = [
    "LocalPreviewStore",
    "PreviewObjectNotFound",
    "PreviewStorageError",
    "PreviewStore",
    "S3PreviewStore",
    "frame_key",
    "sample_key",
    "thumbnail_key",
]
