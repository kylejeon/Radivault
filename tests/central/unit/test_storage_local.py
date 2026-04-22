"""Local-fs object store."""

from __future__ import annotations

from pathlib import Path

import pytest

from radivault_central.storage.base import StoragePathTraversalError
from radivault_central.storage.local import LocalFsObjectStore


def test_put_and_delete_roundtrip(tmp_path: Path):
    store = LocalFsObjectStore(tmp_path / "bucket")
    store.put_object("a/b/c.dcm", b"hello", content_type="application/dicom")
    assert (tmp_path / "bucket" / "a" / "b" / "c.dcm").read_bytes() == b"hello"
    assert store.head_bucket()

    store.delete_objects(["a/b/c.dcm"])
    assert not (tmp_path / "bucket" / "a" / "b" / "c.dcm").exists()


def test_head_bucket_false_for_missing(tmp_path: Path):
    store = LocalFsObjectStore(tmp_path / "x")
    assert store.head_bucket()  # constructor creates it


@pytest.mark.parametrize(
    "bad_key",
    [
        "../escape.dcm",
        "a/../../escape.dcm",
        "a/b/../../../escape.dcm",
        "/abs/path/escape.dcm",
        "..",
        "foo/../../bar.dcm",
        "",
    ],
)
def test_put_rejects_path_traversal(tmp_path: Path, bad_key: str) -> None:
    """H-1: keys that escape the root must be rejected before any write."""

    # Sentinel file outside the bucket — must remain untouched after each attempt.
    outside = tmp_path / "escape.dcm"
    bucket_root = tmp_path / "bucket"
    store = LocalFsObjectStore(bucket_root)

    before = set(bucket_root.rglob("*"))
    with pytest.raises(StoragePathTraversalError):
        store.put_object(bad_key, b"PWNED")

    # No file was written outside root, and the bucket tree is unchanged.
    assert not outside.exists()
    after = set(bucket_root.rglob("*"))
    assert before == after


def test_put_rejects_backslash_and_null_keys(tmp_path: Path) -> None:
    store = LocalFsObjectStore(tmp_path / "bucket")
    with pytest.raises(StoragePathTraversalError):
        store.put_object("a\\b.dcm", b"x")
    with pytest.raises(StoragePathTraversalError):
        store.put_object("a\x00b.dcm", b"x")


def test_delete_ignores_traversal_keys(tmp_path: Path) -> None:
    # Cleanup must never chase a traversal key.
    store = LocalFsObjectStore(tmp_path / "bucket")
    outside = tmp_path / "sentinel.dcm"
    outside.write_bytes(b"keep-me")
    store.delete_objects(["../sentinel.dcm", "/tmp/nope.dcm"])
    assert outside.read_bytes() == b"keep-me"
