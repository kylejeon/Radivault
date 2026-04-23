"""S3 presigned URL minting (FR-63, §6.7.2/5).

Uses boto3 ``generate_presigned_url`` when available. In tests a deterministic
mock signer is injected so we can assert on shape without a network call.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

log = logging.getLogger("radivault_fulfillment.download.presigned")


@dataclass
class MintedUrl:
    url: str
    signature_hash: str  # 16 hex chars


class PresignedSigner:
    """Thin wrapper around boto3 with an override hook for tests."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        boto_client=None,
        override_signer: Callable[[str, str, int], str] | None = None,
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        self._client = boto_client
        self._override = override_signer

    @classmethod
    def build(
        cls,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> PresignedSigner:
        try:
            import boto3
        except ImportError:  # pragma: no cover — not installed in test env
            return cls(bucket=bucket, region=region, endpoint_url=endpoint_url)
        client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        return cls(
            bucket=bucket,
            region=region,
            endpoint_url=endpoint_url,
            boto_client=client,
        )

    def mint(
        self,
        *,
        object_key: str,
        ttl_seconds: int,
        filename: str,
    ) -> MintedUrl:
        if self._override is not None:
            url = self._override(object_key, filename, ttl_seconds)
        elif self._client is not None:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": object_key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=ttl_seconds,
                HttpMethod="GET",
            )
        else:
            # Deterministic fallback for test environments lacking boto3.
            url = _stub_url(
                bucket=self._bucket,
                region=self._region,
                endpoint_url=self._endpoint_url,
                key=object_key,
                ttl=ttl_seconds,
                filename=filename,
            )
        return MintedUrl(url=url, signature_hash=_extract_signature_hash(url))


def _stub_url(
    *,
    bucket: str,
    region: str,
    endpoint_url: str | None,
    key: str,
    ttl: int,
    filename: str,
) -> str:
    """Fallback URL used in tests — mimics SigV4 query style."""
    base = endpoint_url or f"https://s3.{region}.amazonaws.com"
    sig = hashlib.sha256(f"{bucket}/{key}/{ttl}/{filename}".encode()).hexdigest()[:32]
    return (
        f"{base}/{bucket}/{key}?"
        f"X-Amz-Algorithm=AWS4-HMAC-SHA256&"
        f"X-Amz-Expires={ttl}&"
        f"X-Amz-Signature={sig}&"
        f"response-content-disposition=attachment%3B%20filename%3D%22{filename}%22"
    )


def _extract_signature_hash(url: str) -> str:
    """Return a 16-hex-char digest of the URL signature (FR-65)."""
    try:
        qs = parse_qs(urlparse(url).query)
        sig = qs.get("X-Amz-Signature", [""])[0]
        if sig:
            return hashlib.sha256(sig.encode()).hexdigest()[:16]
    except Exception:
        pass
    return hashlib.sha256(url.encode()).hexdigest()[:16]


__all__ = ["MintedUrl", "PresignedSigner"]
