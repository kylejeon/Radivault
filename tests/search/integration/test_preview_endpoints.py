"""Integration tests — buyer browse → preview → sample download endpoints.

dev-spec-buyer-browse-preview FR-API-1 acceptance:
  - thumbnail / frames / sample-download require Bearer auth.
  - preview_status='verified' gate (other states return 403).
  - sample_download_audit row INSERT on successful sample-download.
  - quota INCR enforces daily limit (default 1).
  - sample_instance_uid missing ⇒ 409.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy import select

from radivault_central.db.models import Hospital, SampleDownloadAudit, Study


@pytest.fixture
def verified_study(engine_and_factory):
    """Insert a single ``verified`` study with thumbnail/frame/sample assets."""
    _, factory = engine_and_factory
    with factory() as session:
        hosp = Hospital(
            hospital_id="hosp_preview",
            name="Preview Test Hosp",
            salt_version_current=1,
        )
        session.add(hosp)
        session.flush()
        study = Study(
            pseudo_study_uid="2.25.preview.001",
            hospital_pk=hosp.hospital_pk,
            modality="CT",
            body_part="CHEST",
            n_instances=18,
            n_series=1,
            total_bytes=1024 * 1024,
            central_job_id="job_preview_001",
            gateway_id="gw_preview",
            preview_status="verified",
            preview_thumbnail_key="thumbnails/2.25.preview.001.jpg",
            preview_slice_count=5,
            sample_instance_uid="1.2.840.preview.sop.001",
        )
        session.add(study)
        session.commit()
        session.refresh(study)
    return study


@pytest.fixture
def pending_study(engine_and_factory):
    _, factory = engine_and_factory
    with factory() as session:
        hosp = Hospital(
            hospital_id="hosp_pending",
            name="Pending Test Hosp",
            salt_version_current=1,
        )
        session.add(hosp)
        session.flush()
        study = Study(
            pseudo_study_uid="2.25.preview.002",
            hospital_pk=hosp.hospital_pk,
            modality="MR",
            n_instances=10,
            n_series=1,
            total_bytes=1024,
            central_job_id="job_preview_002",
            gateway_id="gw_preview",
            # Default preview_status='pending'
        )
        session.add(study)
        session.commit()
        session.refresh(study)
    return study


def _seed_preview_assets(app_client, verified_study):
    """Drop a JPEG thumbnail + frames into the LocalPreviewStore root."""
    store = app_client.app.state.preview_store
    root = Path(store._root)
    # Tiny JPEG header + minimal payload (not a real image, sufficient for
    # the router's content-type assertion).
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 60 + b"\xff\xd9"
    (root / "thumbnails").mkdir(parents=True, exist_ok=True)
    (root / "thumbnails" / f"{verified_study.pseudo_study_uid}.jpg").write_bytes(fake_jpeg)
    frames_dir = root / "frames" / verified_study.pseudo_study_uid / "1"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for n in range(1, (verified_study.preview_slice_count or 0) + 1):
        (frames_dir / f"{n}.jpg").write_bytes(fake_jpeg)
    samples_dir = root / "samples" / verified_study.pseudo_study_uid
    samples_dir.mkdir(parents=True, exist_ok=True)
    (samples_dir / f"{verified_study.sample_instance_uid}.dcm").write_bytes(
        b"DICM" + b"\x00" * 256
    )


# ---------------------------------------------------------------------------


def test_thumbnail_requires_auth(app_client, verified_study):
    res = app_client.get(f"/v1/studies/{verified_study.pseudo_study_uid}/thumbnail")
    assert res.status_code == 401
    assert res.json()["error"] == "ERR_AUTH_MISSING"


def test_thumbnail_verified_returns_jpeg(app_client, seeded_buyer, verified_study):
    _seed_preview_assets(app_client, verified_study)
    _, bundle = seeded_buyer
    res = app_client.get(
        f"/v1/studies/{verified_study.pseudo_study_uid}/thumbnail",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("image/jpeg")
    assert "etag" in {k.lower() for k in res.headers.keys()}
    cache_control = res.headers.get("cache-control", "")
    assert "max-age=86400" in cache_control
    assert res.content.startswith(b"\xff\xd8\xff")


def test_thumbnail_pending_returns_403(app_client, seeded_buyer, pending_study):
    _, bundle = seeded_buyer
    res = app_client.get(
        f"/v1/studies/{pending_study.pseudo_study_uid}/thumbnail",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 403
    assert res.json()["error"] == "ERR_PREVIEW_NOT_VERIFIED"


def test_thumbnail_unknown_study_returns_404(app_client, seeded_buyer):
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/studies/2.25.does.not.exist/thumbnail",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 404
    assert res.json()["error"] == "ERR_STUDY_NOT_FOUND"


# ---------------------------------------------------------------------------


def test_frame_returns_jpeg(app_client, seeded_buyer, verified_study):
    _seed_preview_assets(app_client, verified_study)
    _, bundle = seeded_buyer
    res = app_client.get(
        f"/v1/studies/{verified_study.pseudo_study_uid}/series/1/frames/1",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("image/jpeg")


def test_frame_out_of_range_returns_404(app_client, seeded_buyer, verified_study):
    _seed_preview_assets(app_client, verified_study)
    _, bundle = seeded_buyer
    # preview_slice_count=5 → frame 6 is out of range
    res = app_client.get(
        f"/v1/studies/{verified_study.pseudo_study_uid}/series/1/frames/99",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 404
    assert res.json()["error"] == "ERR_FRAME_NOT_FOUND"


def test_frame_pending_returns_403(app_client, seeded_buyer, pending_study):
    _, bundle = seeded_buyer
    res = app_client.get(
        f"/v1/studies/{pending_study.pseudo_study_uid}/series/1/frames/1",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 403
    assert res.json()["error"] == "ERR_PREVIEW_NOT_VERIFIED"


# ---------------------------------------------------------------------------


def test_sample_download_happy_path(
    app_client, seeded_buyer, verified_study, engine_and_factory
):
    _seed_preview_assets(app_client, verified_study)
    _, bundle = seeded_buyer
    res = app_client.post(
        f"/v1/studies/{verified_study.pseudo_study_uid}/sample-download",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "presigned_url" in body
    assert body["instance_uid"] == verified_study.sample_instance_uid
    assert body["study_uid"] == verified_study.pseudo_study_uid
    assert body["size_bytes"] > 0
    assert body["quota_after"]["used"] == 1
    assert body["quota_after"]["limit"] == 1
    assert body["quota_after"]["resets_at"]
    # Confirm audit row.
    _, factory = engine_and_factory
    with factory() as session:
        rows = session.scalars(select(SampleDownloadAudit)).all()
        assert len(rows) == 1
        audit = rows[0]
        assert audit.study_uid == verified_study.pseudo_study_uid
        assert audit.instance_uid == verified_study.sample_instance_uid
        assert audit.status == "issued"
        assert len(audit.presigned_url_hash) == 64  # sha256 hex


def test_sample_download_quota_exceeded(
    app_client, seeded_buyer, verified_study
):
    _seed_preview_assets(app_client, verified_study)
    _, bundle = seeded_buyer
    headers = {"Authorization": f"Bearer {bundle.plaintext}"}
    # First call OK
    r1 = app_client.post(
        f"/v1/studies/{verified_study.pseudo_study_uid}/sample-download",
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    # Second call same day → 429
    r2 = app_client.post(
        f"/v1/studies/{verified_study.pseudo_study_uid}/sample-download",
        headers=headers,
    )
    assert r2.status_code == 429, r2.text
    assert r2.json()["error"] == "ERR_QUOTA_EXCEEDED"


def test_sample_download_pending_returns_403(
    app_client, seeded_buyer, pending_study
):
    _, bundle = seeded_buyer
    res = app_client.post(
        f"/v1/studies/{pending_study.pseudo_study_uid}/sample-download",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 403
    assert res.json()["error"] == "ERR_PREVIEW_NOT_VERIFIED"


def test_sample_download_missing_instance_returns_409(
    app_client, seeded_buyer, engine_and_factory
):
    """Verified study without a sample_instance_uid → 409 ERR_SAMPLE_INSTANCE_MISSING."""
    _, factory = engine_and_factory
    with factory() as session:
        hosp = Hospital(
            hospital_id="hosp_misconfig",
            name="Misconfig Hosp",
            salt_version_current=1,
        )
        session.add(hosp)
        session.flush()
        study = Study(
            pseudo_study_uid="2.25.misconfig.001",
            hospital_pk=hosp.hospital_pk,
            modality="CT",
            n_instances=1,
            n_series=1,
            total_bytes=512,
            central_job_id="job_mc_001",
            gateway_id="gw_mc",
            preview_status="verified",
            preview_thumbnail_key="thumbnails/2.25.misconfig.001.jpg",
            preview_slice_count=1,
            sample_instance_uid=None,  # missing!
        )
        session.add(study)
        session.commit()
    _, bundle = seeded_buyer
    res = app_client.post(
        "/v1/studies/2.25.misconfig.001/sample-download",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 409
    assert res.json()["error"] == "ERR_SAMPLE_INSTANCE_MISSING"


# ---------------------------------------------------------------------------


def test_account_quota_returns_state(app_client, seeded_buyer):
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/account/quota",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["daily_used"] == 0
    assert body["daily_limit"] == 1
    assert body["available"] is True
    assert body["resets_at"]


def test_account_quota_increments_after_sample_download(
    app_client, seeded_buyer, verified_study
):
    _seed_preview_assets(app_client, verified_study)
    _, bundle = seeded_buyer
    headers = {"Authorization": f"Bearer {bundle.plaintext}"}
    app_client.post(
        f"/v1/studies/{verified_study.pseudo_study_uid}/sample-download",
        headers=headers,
    )
    res = app_client.get("/v1/account/quota", headers=headers)
    assert res.status_code == 200
    assert res.json()["daily_used"] == 1
