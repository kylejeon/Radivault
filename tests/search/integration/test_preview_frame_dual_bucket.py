"""Integration test — frame route dual-bucket dispatch (B-4).

jpg-preview-defacing FR-API-1 / dev-spec §7.1 / B-4 (BLOCKER #4).

The single ``GET /v1/studies/{uid}/series/{n}/frames/{m}`` endpoint
dispatches by row presence in ``dicom_preview_frame``:

  * Row exists  → serve from ``previews_store_v2`` (radivault-previews
                  bucket) using the gateway-written key. NO legacy
                  ``study.preview_status`` gate.
  * Row absent  → serve from the legacy ``preview_store`` (radivault-preview
                  bucket) using the original ``frames/{study}/{n}/{m}.jpg``
                  key, with the legacy ``_verified_or_403`` gate.

This file covers the new-pipeline branch end-to-end. The legacy branch
is already exercised by ``tests/search/integration/test_preview_endpoints.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radivault_central.db.models import (
    DicomPreviewFrame,
    Hospital,
    Series,
    Study,
)


@pytest.fixture
def new_pipeline_study(engine_and_factory):
    _, factory = engine_and_factory
    with factory() as session:
        hosp = Hospital(
            hospital_id="hosp_dual_bucket",
            name="Dual Bucket Hosp",
            salt_version_current=1,
        )
        session.add(hosp)
        session.flush()
        # Note: study.preview_status='pending' (default) — legacy gate
        # would 403 every fetch. The new dispatch must NOT consult it.
        study = Study(
            pseudo_study_uid="2.25.dual.bucket.1",
            hospital_pk=hosp.hospital_pk,
            modality="CT",
            body_part="HEAD",
            n_instances=3,
            n_series=1,
            total_bytes=512,
            central_job_id="job_dual_001",
            gateway_id="gw_dual",
        )
        session.add(study)
        session.flush()
        ser = Series(
            study_pk=study.study_pk,
            pseudo_series_uid="ser-dual-1",
            modality="CT",
            body_part="HEAD",
            series_number=1,
            n_instances=3,
            preview_status="generated",
            preview_frame_count=3,
            preview_deface_method="afni_refacer_v0_7",
            preview_deface_decision="required",
            preview_pipeline_version="0.1.0",
        )
        session.add(ser)
        session.flush()
        for i in range(3):
            session.add(
                DicomPreviewFrame(
                    pseudo_series_uid="ser-dual-1",
                    pseudo_study_uid="2.25.dual.bucket.1",
                    frame_idx=i,
                    minio_key=(
                        f"previews/2.25.dual.bucket.1/ser-dual-1/{i:04d}.jpg"
                    ),
                    width=512,
                    height=512,
                    byte_size=128,
                    sha256="0" * 64,
                    phi_scrub_method="afni_refacer_v0_7",
                )
            )
        session.commit()
        session.refresh(study)
    return study


def _seed_v2_jpegs(app_client) -> bytes:
    """Drop fake JPEGs into the v2 (new pipeline) preview store at the
    keys the gateway preview_pipeline writes. Returns the JPEG bytes."""
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10NEW PIPELINE JPG\xff\xd9"
    store = app_client.app.state.previews_store_v2
    root = Path(store._root)
    series_dir = root / "previews" / "2.25.dual.bucket.1" / "ser-dual-1"
    series_dir.mkdir(parents=True, exist_ok=True)
    for i in range(3):
        (series_dir / f"{i:04d}.jpg").write_bytes(fake_jpeg)
    return fake_jpeg


def test_frame_new_pipeline_serves_from_v2_bucket_no_legacy_gate(
    app_client, seeded_buyer, new_pipeline_study
):
    """Happy path: dicom_preview_frame row exists → serves from
    radivault-previews bucket, ignores study.preview_status='pending'."""
    fake_jpeg = _seed_v2_jpegs(app_client)
    _, bundle = seeded_buyer
    res = app_client.get(
        f"/v1/studies/{new_pipeline_study.pseudo_study_uid}/series/1/frames/1",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("image/jpeg")
    assert res.content == fake_jpeg


def test_frame_new_pipeline_translates_1based_to_0based_key(
    app_client, seeded_buyer, new_pipeline_study
):
    """Wire frame_num is 1-based (matches §7.1 + sibling BFF route).
    Frame 1 must map to key ``...0000.jpg`` not ``...0001.jpg``.
    """
    _seed_v2_jpegs(app_client)
    _, bundle = seeded_buyer

    # Place a sentinel byte in the 0000 frame and a different one in 0001
    # so we can prove which frame_num pulled which key.
    store = app_client.app.state.previews_store_v2
    root = Path(store._root)
    series_dir = root / "previews" / "2.25.dual.bucket.1" / "ser-dual-1"
    sentinel_0 = b"\xff\xd8\xffSENTINEL_FRAME_0_KEY_0000\xff\xd9"
    sentinel_1 = b"\xff\xd8\xffSENTINEL_FRAME_1_KEY_0001\xff\xd9"
    (series_dir / "0000.jpg").write_bytes(sentinel_0)
    (series_dir / "0001.jpg").write_bytes(sentinel_1)

    res1 = app_client.get(
        f"/v1/studies/{new_pipeline_study.pseudo_study_uid}/series/1/frames/1",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res1.status_code == 200
    assert res1.content == sentinel_0, "frame_num=1 must read 0-based key 0000"

    res2 = app_client.get(
        f"/v1/studies/{new_pipeline_study.pseudo_study_uid}/series/1/frames/2",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res2.status_code == 200
    assert res2.content == sentinel_1, "frame_num=2 must read 0-based key 0001"


def test_frame_new_pipeline_missing_blob_returns_404(
    app_client, seeded_buyer, new_pipeline_study
):
    """DB row exists but the v2 bucket has no JPG → 404 (not 500)."""
    # Note: we DO NOT seed any JPGs. The dicom_preview_frame row exists
    # so we go down the v2 path; the blob is missing → 404.
    _, bundle = seeded_buyer
    res = app_client.get(
        f"/v1/studies/{new_pipeline_study.pseudo_study_uid}/series/1/frames/1",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 404
    assert res.json()["error"] == "ERR_FRAME_NOT_FOUND"


def test_frame_new_pipeline_unknown_frame_idx_returns_404(
    app_client, seeded_buyer, new_pipeline_study
):
    """Series exists with 3 frames; requesting frame 99 → 404 with
    ``preview_unavailable``-style detail (no legacy slice_count gate)."""
    _seed_v2_jpegs(app_client)
    _, bundle = seeded_buyer
    res = app_client.get(
        f"/v1/studies/{new_pipeline_study.pseudo_study_uid}/series/1/frames/99",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 404


def test_frame_new_pipeline_does_not_403_on_legacy_pending_gate(
    app_client, seeded_buyer, new_pipeline_study
):
    """Regression — even though study.preview_status='pending' (legacy
    enum default), the new pipeline must serve. Gate must NOT trigger.
    """
    _seed_v2_jpegs(app_client)
    _, bundle = seeded_buyer
    # Re-confirm: study.preview_status is the legacy enum default 'pending'
    assert new_pipeline_study.preview_status == "pending"
    res = app_client.get(
        f"/v1/studies/{new_pipeline_study.pseudo_study_uid}/series/1/frames/1",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    # Legacy code would have returned 403 ERR_PREVIEW_NOT_VERIFIED here.
    assert res.status_code == 200, res.text
