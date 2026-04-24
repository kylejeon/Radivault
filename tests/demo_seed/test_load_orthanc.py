"""Unit tests for scripts/demo_seed/load_orthanc.py.

We avoid a real HTTP/Orthanc server — instead we exercise the
payload builder and marker logic directly, and point a fake
``httpx.Client`` at the upload function where needed.
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
import pytest


def _make_cache(tmp_path: Path) -> Path:
    """Build a fake cache dir with one completed + one unfinished study."""
    cache = tmp_path / "cache"
    done = cache / "TEST-CT" / "study-A"
    done.mkdir(parents=True)
    (done / "im1.dcm").write_bytes(b"DICMAAA")
    (done / "im2.dcm").write_bytes(b"DICMBBB")
    (done / "_done.marker").touch()

    pending = cache / "TEST-CT" / "study-B"
    pending.mkdir(parents=True)
    (pending / "im1.dcm").write_bytes(b"DICMXYZ")
    # note: no _done.marker, so it should be skipped by _iter_study_dirs.
    return cache


def test_iter_study_dirs_only_returns_completed(orthanc_mod, tmp_path):
    cache = _make_cache(tmp_path)
    studies = orthanc_mod._iter_study_dirs(cache)
    assert len(studies) == 1
    assert studies[0].name == "study-A"


def test_multipart_payload_contains_boundary_and_dicom_parts(orthanc_mod, tmp_path):
    f1 = tmp_path / "a.dcm"
    f1.write_bytes(b"\x00FILE-A\x00")
    f2 = tmp_path / "b.dcm"
    f2.write_bytes(b"\x00FILE-B\x00")
    body = orthanc_mod._multipart_payload([f1, f2], boundary="bnd-123")

    # Opening boundary present.
    assert b"--bnd-123" in body
    # Proper terminator.
    assert body.rstrip().endswith(b"--bnd-123--")
    # Both DICOM Content-Type parts.
    assert body.count(b"Content-Type: application/dicom") == 2
    # Payload bytes preserved.
    assert b"FILE-A" in body and b"FILE-B" in body


def test_auth_header_is_basic_and_roundtrips(orthanc_mod):
    header = orthanc_mod._auth_header("orthanc", "orthanc")
    assert header.startswith("Basic ")
    token = header.split(" ", 1)[1]
    assert base64.b64decode(token).decode() == "orthanc:orthanc"


def test_check_orthanc_raises_exit_3_on_failure(orthanc_mod):
    """If Orthanc returns 5xx or is down, check_orthanc must SystemExit(3)."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://orthanc.invalid", transport=transport)
    try:
        with pytest.raises(SystemExit) as exc:
            orthanc_mod.check_orthanc(client)
        assert exc.value.code == 3
    finally:
        client.close()


def test_upload_study_posts_stow_rs(orthanc_mod, tmp_path):
    """upload_study posts multipart/related to /dicom-web/studies."""
    study = tmp_path / "study"
    study.mkdir()
    (study / "a.dcm").write_bytes(b"AAA")
    (study / "b.dcm").write_bytes(b"BBB")

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["content_type"] = request.headers["content-type"]
        captured["body_len"] = len(request.content)
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://orthanc", transport=transport)
    try:
        n_files, status = orthanc_mod.upload_study(client, study, boundary="bnd-xy")
    finally:
        client.close()

    assert n_files == 2
    assert status == 200
    assert captured["url"].endswith("/dicom-web/studies")
    assert "multipart/related" in captured["content_type"]
    assert "bnd-xy" in captured["content_type"]
    assert captured["body_len"] > 0
