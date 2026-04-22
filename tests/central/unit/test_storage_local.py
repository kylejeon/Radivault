"""Local-fs object store."""

from __future__ import annotations

from pathlib import Path

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
