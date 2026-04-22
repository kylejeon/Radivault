"""S3 object store startup and put_object guards (H-2).

Covers the two fixes from QA round 1 H-2:
  * Fail-closed SSE-KMS enforcement — operator must opt into unencrypted.
  * Fail-closed https-only transport — ``http://`` endpoints require an
    explicit ``allow_insecure=True`` dev/test override.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from botocore.stub import Stubber

from radivault_central.storage.base import ObjectStoreError
from radivault_central.storage.s3 import S3ObjectStore

# --- Startup guards ---------------------------------------------------------


def test_startup_rejects_missing_kms_when_not_allowed() -> None:
    with pytest.raises(ObjectStoreError, match="SSE-KMS"):
        S3ObjectStore(
            bucket="rv-ingest",
            region="ap-northeast-2",
            endpoint_url="https://s3.ap-northeast-2.amazonaws.com",
            kms_key_arn=None,
        )


def test_startup_allows_missing_kms_when_opted_in(caplog) -> None:
    with caplog.at_level("WARNING", logger="radivault_central.storage.s3"):
        store = S3ObjectStore(
            bucket="rv-ingest",
            region="ap-northeast-2",
            endpoint_url="https://s3.ap-northeast-2.amazonaws.com",
            kms_key_arn=None,
            allow_unencrypted=True,
        )
    assert store._kms_key_arn is None
    assert any(
        "WITHOUT SSE-KMS" in rec.message or "unencrypted" in rec.message.lower()
        for rec in caplog.records
    )


def test_startup_rejects_http_endpoint_by_default() -> None:
    with pytest.raises(ObjectStoreError, match="http://"):
        S3ObjectStore(
            bucket="rv-ingest",
            region="ap-northeast-2",
            endpoint_url="http://minio:9000",
            kms_key_arn="arn:aws:kms:ap-northeast-2:111111111111:key/abcd",
        )


def test_startup_allows_http_endpoint_when_opted_in(caplog) -> None:
    with caplog.at_level("WARNING", logger="radivault_central.storage.s3"):
        store = S3ObjectStore(
            bucket="rv-ingest",
            region="ap-northeast-2",
            endpoint_url="http://minio:9000",
            kms_key_arn="arn:aws:kms:ap-northeast-2:111111111111:key/abcd",
            allow_insecure=True,
        )
    assert store._allow_insecure is True
    assert any(
        "insecure" in rec.message.lower() or "http" in rec.message.lower() for rec in caplog.records
    )


def test_startup_rejects_unknown_scheme() -> None:
    with pytest.raises(ObjectStoreError, match="scheme"):
        S3ObjectStore(
            bucket="rv-ingest",
            region="ap-northeast-2",
            endpoint_url="ftp://storage",
            kms_key_arn="arn:aws:kms:ap-northeast-2:111111111111:key/abcd",
        )


# --- put_object emits SSE-KMS headers ---------------------------------------


def test_put_object_sends_sse_kms_headers() -> None:
    """When kms_key_arn is set, every PUT carries SSE-KMS params."""

    store = S3ObjectStore(
        bucket="rv-ingest",
        region="ap-northeast-2",
        endpoint_url="https://s3.ap-northeast-2.amazonaws.com",
        kms_key_arn="arn:aws:kms:ap-northeast-2:111111111111:key/abcd",
    )

    with Stubber(store._client) as stub:
        stub.add_response(
            "put_object",
            {"ETag": '"deadbeef"'},
            expected_params={
                "Bucket": "rv-ingest",
                "Key": "prod/ab/hosp/study/study/0001.dcm",
                "Body": _AnyBytesIO(),
                "ContentType": "application/dicom",
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": "arn:aws:kms:ap-northeast-2:111111111111:key/abcd",
            },
        )
        store.put_object(
            "prod/ab/hosp/study/study/0001.dcm",
            b"fake-dicom",
            content_type="application/dicom",
        )
        stub.assert_no_pending_responses()


def test_put_object_skips_sse_when_unencrypted_allowed() -> None:
    """When operator opted into allow_unencrypted, no SSE headers are sent."""

    store = S3ObjectStore(
        bucket="rv-ingest",
        region="ap-northeast-2",
        endpoint_url="https://s3.ap-northeast-2.amazonaws.com",
        kms_key_arn=None,
        allow_unencrypted=True,
    )

    with Stubber(store._client) as stub:
        stub.add_response(
            "put_object",
            {"ETag": '"deadbeef"'},
            expected_params={
                "Bucket": "rv-ingest",
                "Key": "dev/ab/hosp/study/study/0001.dcm",
                "Body": _AnyBytesIO(),
                "ContentType": "application/dicom",
            },
        )
        store.put_object(
            "dev/ab/hosp/study/study/0001.dcm",
            b"fake-dicom",
            content_type="application/dicom",
        )
        stub.assert_no_pending_responses()


class _AnyBytesIO:
    """botocore Stubber equality helper — matches any BytesIO payload."""

    def __eq__(self, other: object) -> bool:  # pragma: no cover — trivial
        return isinstance(other, BytesIO)

    def __repr__(self) -> str:  # pragma: no cover
        return "<any-BytesIO>"
