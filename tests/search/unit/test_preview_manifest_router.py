"""Unit + integration tests for ``GET /v1/studies/{uid}/preview-manifest``.

jpg-preview-defacing FR-API-2 / dev-spec §7.2 / B-3 (BLOCKER #3).

Coverage:

* legacy study (no ``series`` rows OR all-pending) → 404
* all-quarantined study → 200 with frame_count=0 + status='quarantined'
* mixed status (one generated + one quarantined) → 200 with both rows
* single happy-path series → 200 + scrub_method='afni_refacer_v0_7'

The test fixture seeds the ``central`` Study + Series + DicomPreviewFrame
+ PhiScrubAudit tables directly; no gateway / sidecar is invoked.
"""

from __future__ import annotations

import pytest

from radivault_central.db.models import (
    DicomPreviewFrame,
    Hospital,
    PhiScrubAudit,
    Series,
    Study,
)


def _seed_study(factory, *, pseudo_study_uid: str, hospital_id: str) -> Study:
    with factory() as session:
        hosp = Hospital(
            hospital_id=hospital_id,
            name="Manifest Test Hosp",
            salt_version_current=1,
        )
        session.add(hosp)
        session.flush()
        study = Study(
            pseudo_study_uid=pseudo_study_uid,
            hospital_pk=hosp.hospital_pk,
            modality="MR",
            body_part="BRAIN",
            n_instances=10,
            n_series=1,
            total_bytes=1024,
            central_job_id=f"job_{pseudo_study_uid}",
            gateway_id="gw_test",
            preview_status="pending",
        )
        session.add(study)
        session.commit()
        session.refresh(study)
    return study


def _add_series(
    factory,
    study: Study,
    *,
    pseudo_series_uid: str,
    series_number: int,
    modality: str = "MR",
    body_part: str = "BRAIN",
    preview_status: str = "generated",
    preview_frame_count: int = 0,
    preview_deface_method: str | None = None,
    preview_deface_decision: str | None = None,
) -> Series:
    with factory() as session:
        s = Series(
            study_pk=study.study_pk,
            pseudo_series_uid=pseudo_series_uid,
            modality=modality,
            body_part=body_part,
            series_number=series_number,
            n_instances=preview_frame_count or 1,
            preview_status=preview_status,
            preview_frame_count=preview_frame_count,
            preview_deface_method=preview_deface_method,
            preview_deface_decision=preview_deface_decision,
            preview_pipeline_version="0.1.0",
        )
        session.add(s)
        session.commit()
        session.refresh(s)
    return s


def _add_frames(factory, *, pseudo_study_uid: str, pseudo_series_uid: str, n: int) -> None:
    with factory() as session:
        for i in range(n):
            session.add(
                DicomPreviewFrame(
                    pseudo_series_uid=pseudo_series_uid,
                    pseudo_study_uid=pseudo_study_uid,
                    frame_idx=i,
                    minio_key=(
                        f"previews/{pseudo_study_uid}/{pseudo_series_uid}/"
                        f"{i:04d}.jpg"
                    ),
                    width=512,
                    height=512,
                    byte_size=12345,
                    sha256="0" * 64,
                    phi_scrub_method="afni_refacer_v0_7",
                    source_instance_uid_pseudo=None,
                )
            )
        session.commit()


def _add_audit(
    factory,
    *,
    pseudo_study_uid: str,
    pseudo_series_uid: str,
    outcome: str = "success",
    phi_scrub_method: str = "afni_refacer_v0_7",
) -> None:
    with factory() as session:
        session.add(
            PhiScrubAudit(
                pseudo_study_uid=pseudo_study_uid,
                pseudo_series_uid=pseudo_series_uid,
                modality="MR",
                body_part="BRAIN",
                deface_decision="required",
                deface_decision_reason="BodyPartExamined=BRAIN",
                phi_scrub_method=phi_scrub_method,
                sidecar_image_tag="radivault/deface-sidecar:0.1.0",
                afni_version="AFNI_24.0.00",
                duration_ms=12_345,
                outcome=outcome,
                error_code=None,
                error_detail=None,
                pipeline_version="0.1.0",
            )
        )
        session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_manifest_legacy_study_returns_404(app_client, seeded_buyer, engine_and_factory):
    """A study with no Series rows has no new-pipeline manifest — 404."""
    _, factory = engine_and_factory
    _, bundle = seeded_buyer
    _seed_study(
        factory,
        pseudo_study_uid="2.25.legacy.no.pipeline",
        hospital_id="hosp_legacy",
    )
    res = app_client.get(
        "/v1/studies/2.25.legacy.no.pipeline/preview-manifest",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 404, res.text
    body = res.json()
    assert body["error"] == "ERR_STUDY_NOT_FOUND"


def test_manifest_all_pending_series_returns_404(
    app_client, seeded_buyer, engine_and_factory
):
    """Series rows exist but every preview_status='pending' (legacy
    backfill default) → 404 so the BFF stays on the SliceViewer."""
    _, factory = engine_and_factory
    _, bundle = seeded_buyer
    study = _seed_study(
        factory,
        pseudo_study_uid="2.25.legacy.all.pending",
        hospital_id="hosp_pending",
    )
    _add_series(
        factory,
        study,
        pseudo_series_uid="ser-pending-1",
        series_number=1,
        preview_status="pending",
        preview_frame_count=0,
    )
    res = app_client.get(
        "/v1/studies/2.25.legacy.all.pending/preview-manifest",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 404, res.text


def test_manifest_all_quarantined_series_returns_200(
    app_client, seeded_buyer, engine_and_factory
):
    """Every series quarantined → 200 with all rows status='quarantined'
    + frame_count=0 + scrub_method='deface_failed_runtime'.
    """
    _, factory = engine_and_factory
    _, bundle = seeded_buyer
    study = _seed_study(
        factory,
        pseudo_study_uid="2.25.q.all",
        hospital_id="hosp_q",
    )
    _add_series(
        factory,
        study,
        pseudo_series_uid="ser-q-1",
        series_number=1,
        preview_status="quarantined",
        preview_frame_count=0,
        preview_deface_method="deface_failed_runtime",
        preview_deface_decision="required",
    )
    _add_audit(
        factory,
        pseudo_study_uid="2.25.q.all",
        pseudo_series_uid="ser-q-1",
        outcome="quarantine_runtime",
        phi_scrub_method="deface_failed_runtime",
    )
    res = app_client.get(
        "/v1/studies/2.25.q.all/preview-manifest",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["pseudo_study_uid"] == "2.25.q.all"
    assert body["pipeline_version"] == "0.1.0"
    assert len(body["series"]) == 1
    s = body["series"][0]
    assert s["status"] == "quarantined"
    assert s["frame_count"] == 0
    assert s["scrub_method"] == "deface_failed_runtime"
    assert s["first_frame_url"] is None  # quarantined → no fetchable frame


def test_manifest_mixed_status_returns_both_rows(
    app_client, seeded_buyer, engine_and_factory
):
    """One generated + one quarantined → 2 rows, only the generated has
    a first_frame_url."""
    _, factory = engine_and_factory
    _, bundle = seeded_buyer
    study = _seed_study(
        factory,
        pseudo_study_uid="2.25.mix.1",
        hospital_id="hosp_mix",
    )
    _add_series(
        factory,
        study,
        pseudo_series_uid="ser-mix-1",
        series_number=1,
        preview_status="generated",
        preview_frame_count=3,
        preview_deface_method="afni_refacer_v0_7",
        preview_deface_decision="required",
    )
    _add_frames(
        factory,
        pseudo_study_uid="2.25.mix.1",
        pseudo_series_uid="ser-mix-1",
        n=3,
    )
    _add_audit(
        factory,
        pseudo_study_uid="2.25.mix.1",
        pseudo_series_uid="ser-mix-1",
    )
    _add_series(
        factory,
        study,
        pseudo_series_uid="ser-mix-2",
        series_number=2,
        preview_status="quarantined",
        preview_frame_count=0,
        preview_deface_method="deface_failed_runtime",
        preview_deface_decision="required",
    )
    _add_audit(
        factory,
        pseudo_study_uid="2.25.mix.1",
        pseudo_series_uid="ser-mix-2",
        outcome="quarantine_runtime",
        phi_scrub_method="deface_failed_runtime",
    )
    res = app_client.get(
        "/v1/studies/2.25.mix.1/preview-manifest",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["series"]) == 2
    by_num = {s["series_num"]: s for s in body["series"]}
    assert by_num[1]["status"] == "generated"
    assert by_num[1]["frame_count"] == 3
    assert by_num[1]["scrub_method"] == "afni_refacer_v0_7"
    assert by_num[1]["first_frame_url"] == (
        "/api/studies/2.25.mix.1/series/1/frames/0"
    )
    assert by_num[2]["status"] == "quarantined"
    assert by_num[2]["frame_count"] == 0
    assert by_num[2]["scrub_method"] == "deface_failed_runtime"
    assert by_num[2]["first_frame_url"] is None


def test_manifest_single_happy_path_series_returns_200(
    app_client, seeded_buyer, engine_and_factory
):
    """One generated series → 200 + 1 row + scrub_method=afni."""
    _, factory = engine_and_factory
    _, bundle = seeded_buyer
    study = _seed_study(
        factory,
        pseudo_study_uid="2.25.happy.1",
        hospital_id="hosp_happy",
    )
    _add_series(
        factory,
        study,
        pseudo_series_uid="ser-happy",
        series_number=1,
        preview_status="generated",
        preview_frame_count=52,
        preview_deface_method="afni_refacer_v0_7",
        preview_deface_decision="required",
    )
    _add_frames(
        factory,
        pseudo_study_uid="2.25.happy.1",
        pseudo_series_uid="ser-happy",
        n=52,
    )
    _add_audit(
        factory,
        pseudo_study_uid="2.25.happy.1",
        pseudo_series_uid="ser-happy",
    )
    res = app_client.get(
        "/v1/studies/2.25.happy.1/preview-manifest",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deface_method"] == "afni_refacer_v0_7"
    assert len(body["series"]) == 1
    s = body["series"][0]
    assert s["pseudo_series_uid"] == "ser-happy"
    assert s["modality"] == "MR"
    assert s["body_part"] == "BRAIN"
    assert s["frame_count"] == 52
    assert s["status"] == "generated"
    assert s["scrub_method"] == "afni_refacer_v0_7"
    assert s["deface_decision"] == "required"
    assert s["first_frame_url"] == (
        "/api/studies/2.25.happy.1/series/1/frames/0"
    )


def test_manifest_unauth_returns_401(app_client, engine_and_factory):
    res = app_client.get("/v1/studies/2.25.x/preview-manifest")
    assert res.status_code == 401
    assert res.json()["error"] == "ERR_AUTH_MISSING"


def test_manifest_unknown_study_returns_404(app_client, seeded_buyer):
    _, bundle = seeded_buyer
    res = app_client.get(
        "/v1/studies/2.25.does.not.exist/preview-manifest",
        headers={"Authorization": f"Bearer {bundle.plaintext}"},
    )
    assert res.status_code == 404
    assert res.json()["error"] == "ERR_STUDY_NOT_FOUND"
