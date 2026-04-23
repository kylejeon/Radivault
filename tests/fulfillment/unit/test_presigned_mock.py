"""PresignedSigner — deterministic fallback shape + signature_hash extraction."""

from __future__ import annotations

import hashlib

from radivault_fulfillment.download.presigned import PresignedSigner


def test_fallback_stub_contains_sigv4_markers() -> None:
    signer = PresignedSigner(
        bucket="radivault-test",
        region="ap-northeast-2",
        endpoint_url=None,
    )
    minted = signer.mint(
        object_key="ingest/aa/hosp/2.25.x/00001.dcm",
        ttl_seconds=86400,
        filename="00001.dcm",
    )
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in minted.url
    assert "X-Amz-Expires=86400" in minted.url
    assert "X-Amz-Signature=" in minted.url
    assert "response-content-disposition" in minted.url
    assert len(minted.signature_hash) == 16


def test_signature_hash_is_deterministic() -> None:
    signer = PresignedSigner(bucket="b", region="r", endpoint_url=None)
    a = signer.mint(object_key="k1", ttl_seconds=300, filename="x.dcm")
    b = signer.mint(object_key="k1", ttl_seconds=300, filename="x.dcm")
    assert a.signature_hash == b.signature_hash


def test_override_signer_used() -> None:
    fake = []

    def _sign(key, filename, ttl):
        fake.append((key, filename, ttl))
        return (
            f"https://example/{key}?X-Amz-Signature={hashlib.sha256(key.encode()).hexdigest()[:32]}"
        )

    signer = PresignedSigner(bucket="b", region="r", endpoint_url=None, override_signer=_sign)
    minted = signer.mint(object_key="key1", ttl_seconds=60, filename="f.dcm")
    assert minted.url.startswith("https://example/key1")
    assert fake == [("key1", "f.dcm", 60)]
