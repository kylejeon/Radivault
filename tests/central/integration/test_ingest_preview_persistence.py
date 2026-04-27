"""Integration test — central ingest persists ``manifest.preview`` block.

jpg-preview-defacing FR-PREVIEW-12 / FR-PREVIEW-13 / FR-AUDIT-1 / B-5
(BLOCKER #5).

The gateway preview_pipeline emits a ``preview`` block on the v2.2
manifest. Central must:

  1. UPDATE ``series.preview_*`` (status, frame_count, deface_method,
     deface_decision, generated_at, pipeline_version)
  2. INSERT N rows into ``dicom_preview_frame``
  3. INSERT 1 row into ``phi_scrub_audit`` per series
  4. Inside the same transaction as the existing study/series writes
     so partial failure is impossible.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from radivault_central.app import create_app
from radivault_central.auth.tokens import generate_token
from radivault_central.config import Settings
from radivault_central.db.models import (
    AuthToken,
    Base,
    DicomPreviewFrame,
    Hospital,
    PhiScrubAudit,
    Series,
)
from radivault_central.db.session import get_engine, reset_for_tests
from radivault_central.storage.local import LocalFsObjectStore


@pytest.fixture
def built_app(tmp_path: Path) -> Iterator[tuple[TestClient, str, sessionmaker]]:
    reset_for_tests()
    db_path = tmp_path / "central.db"
    settings = Settings()
    settings.app.env = "test"
    settings.db.dsn = f"sqlite+pysqlite:///{db_path}"
    settings.storage.provider = "local"
    settings.storage.local_root = str(tmp_path / "store")
    settings.observability.log_level = "WARNING"

    engine = get_engine(settings.db.dsn, pool_size=2, max_overflow=0)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        hospital = Hospital(
            hospital_id="hosp_pp",
            name="Preview Persist Hospital",
            salt_version_current=1,
            allowed_ruleset_versions=["v0.1.0"],
            max_instances_per_study=5000,
            max_study_bytes=20 * 1024 * 1024 * 1024,
        )
        session.add(hospital)
        session.flush()
        bundle = generate_token()
        session.add(
            AuthToken(
                hospital_pk=hospital.hospital_pk,
                token_kid=bundle.kid,
                token_hash=bundle.hash,
            )
        )
        session.commit()
    engine.dispose()
    reset_for_tests()

    app = create_app(settings, testing=False)
    app.state.redis = FakeStrictRedis()
    app.state.object_store = LocalFsObjectStore(settings.storage.local_root)
    for m in app.user_middleware:
        if m.cls.__name__ in {"IdempotencyMiddleware", "RateLimitMiddleware"}:
            m.kwargs["redis_client"] = app.state.redis

    with TestClient(app) as client:
        yield client, bundle.plaintext, app.state.session_factory


def _build_manifest_with_preview(
    files: list[tuple[str, bytes]],
    *,
    pseudo_study_uid: str = "2.25.preview.persist.1",
    preview_block: dict | None = None,
) -> dict:
    """Build a v2.2 manifest with optional ``preview`` block."""
    files_meta = [
        {
            "filename": n,
            "sha256": hashlib.sha256(d).hexdigest(),
            "bytes": len(d),
        }
        for n, d in files
    ]
    manifest = {
        "manifest_version": 2,
        "gateway_id": "gw_pp",
        "hospital_id": "hosp_pp",
        "pseudo_study_uid": pseudo_study_uid,
        "modalities": ["MR"],
        "n_instances": len(files_meta),
        "total_bytes": sum(f["bytes"] for f in files_meta),
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt_version": 1,
            "method_code_sequence": ["113100"],
        },
        "anonymization_flag": "fully_anonymized",
        "files": files_meta,
        "generated_at": "2026-04-27T10:00:00Z",
        # v2 series array — preview block series_num references these
        "series": [
            {
                "pseudo_series_uid": f"{pseudo_study_uid}.s1",
                "series_num": 1,
                "modality": "MR",
                "body_part": "BRAIN",
                "n_instances": len(files_meta),
            }
        ],
    }
    if preview_block is not None:
        manifest["preview"] = preview_block
    return manifest


def _post(client, token, manifest, files, key):
    payload = [
        (
            "manifest",
            ("manifest.json", json.dumps(manifest).encode(), "application/json"),
        ),
    ]
    for name, data in files:
        payload.append(("files", (name, data, "application/dicom")))
    return client.post(
        "/v1/ingest/studies",
        files=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )


def test_ingest_with_preview_block_persists_all_three_writes(built_app):
    """Happy path: manifest.preview with one generated series → series row
    UPDATEd + N frame rows INSERTed + 1 audit row INSERTed."""
    client, token, factory = built_app
    files = [("0001.dcm", b"dicom-1"), ("0002.dcm", b"dicom-2")]
    pseudo_study_uid = "2.25.pp.happy"
    pseudo_series_uid = f"{pseudo_study_uid}.s1"

    preview_block = {
        "skipped": False,
        "reason": None,
        "pipeline_version": "0.1.0",
        "series": [
            {
                "pseudo_series_uid": pseudo_series_uid,
                "series_num": 1,
                "modality": "MR",
                "body_part": "BRAIN",
                "preview_status": "generated",
                "deface_decision": "required",
                "deface_decision_reason": "BodyPartExamined=BRAIN",
                "phi_scrub_method": "afni_refacer_v0_7",
                "frame_count": 3,
                "frames": [
                    {
                        "frame_idx": i,
                        "minio_key": (
                            f"previews/{pseudo_study_uid}/"
                            f"{pseudo_series_uid}/{i:04d}.jpg"
                        ),
                        "width": 512,
                        "height": 512,
                        "byte_size": 12345,
                        "sha256": "a" * 64,
                        "phi_scrub_method": "afni_refacer_v0_7",
                    }
                    for i in range(3)
                ],
                "sidecar_image_tag": "radivault/deface-sidecar:0.1.0",
                "afni_version": "AFNI_24.0.00",
                "duration_ms": 35_000,
                "outcome": "success",
                "error_code": None,
                "error_detail": None,
            }
        ],
    }

    manifest = _build_manifest_with_preview(
        files,
        pseudo_study_uid=pseudo_study_uid,
        preview_block=preview_block,
    )
    r = _post(client, token, manifest, files, key="01HX-PP-HAPPY-0000000000")
    assert r.status_code == 201, r.text

    with factory() as session:
        # 1) Series row UPDATEd with preview_*
        series_row = session.scalar(
            select(Series).where(Series.pseudo_series_uid == pseudo_series_uid)
        )
        assert series_row is not None
        assert series_row.preview_status == "generated"
        assert series_row.preview_frame_count == 3
        assert series_row.preview_deface_decision == "required"
        assert series_row.preview_deface_method == "afni_refacer_v0_7"
        assert series_row.preview_pipeline_version == "0.1.0"
        assert series_row.preview_generated_at is not None

        # 2) 3 dicom_preview_frame rows INSERTed
        frames = session.scalars(
            select(DicomPreviewFrame).where(
                DicomPreviewFrame.pseudo_series_uid == pseudo_series_uid
            )
        ).all()
        assert len(frames) == 3
        keys = sorted(f.minio_key for f in frames)
        assert keys == [
            f"previews/{pseudo_study_uid}/{pseudo_series_uid}/0000.jpg",
            f"previews/{pseudo_study_uid}/{pseudo_series_uid}/0001.jpg",
            f"previews/{pseudo_study_uid}/{pseudo_series_uid}/0002.jpg",
        ]
        for f in frames:
            assert f.width == 512
            assert f.height == 512
            assert f.phi_scrub_method == "afni_refacer_v0_7"
            assert f.pseudo_study_uid == pseudo_study_uid

        # 3) 1 phi_scrub_audit row INSERTed
        audits = session.scalars(
            select(PhiScrubAudit).where(
                PhiScrubAudit.pseudo_series_uid == pseudo_series_uid
            )
        ).all()
        assert len(audits) == 1
        a = audits[0]
        assert a.pseudo_study_uid == pseudo_study_uid
        assert a.modality == "MR"
        assert a.body_part == "BRAIN"
        assert a.deface_decision == "required"
        assert a.deface_decision_reason == "BodyPartExamined=BRAIN"
        assert a.phi_scrub_method == "afni_refacer_v0_7"
        assert a.sidecar_image_tag == "radivault/deface-sidecar:0.1.0"
        assert a.afni_version == "AFNI_24.0.00"
        assert a.duration_ms == 35_000
        assert a.outcome == "success"
        assert a.error_code is None
        assert a.error_detail is None
        assert a.pipeline_version == "0.1.0"


def test_ingest_with_preview_block_quarantined_no_frames(built_app):
    """Quarantined series → series UPDATEd, dicom_preview_frame stays
    empty, audit row records outcome=quarantine_runtime."""
    client, token, factory = built_app
    files = [("0001.dcm", b"d-1")]
    pseudo_study_uid = "2.25.pp.quar"
    pseudo_series_uid = f"{pseudo_study_uid}.s1"

    preview_block = {
        "skipped": False,
        "pipeline_version": "0.1.0",
        "series": [
            {
                "pseudo_series_uid": pseudo_series_uid,
                "series_num": 1,
                "modality": "MR",
                "body_part": "BRAIN",
                "preview_status": "quarantined",
                "deface_decision": "required",
                "deface_decision_reason": "BodyPartExamined=BRAIN",
                "phi_scrub_method": "deface_failed_runtime",
                "frame_count": 0,
                "frames": [],
                "sidecar_image_tag": None,
                "afni_version": None,
                "duration_ms": 12_000,
                "outcome": "quarantine_runtime",
                "error_code": "AFNI_CRASH",
                "error_detail": "afni dumped core",
            }
        ],
    }

    manifest = _build_manifest_with_preview(
        files,
        pseudo_study_uid=pseudo_study_uid,
        preview_block=preview_block,
    )
    r = _post(client, token, manifest, files, key="01HX-PP-QUAR-00000000000")
    assert r.status_code == 201, r.text

    with factory() as session:
        series_row = session.scalar(
            select(Series).where(Series.pseudo_series_uid == pseudo_series_uid)
        )
        assert series_row.preview_status == "quarantined"
        assert series_row.preview_frame_count == 0
        assert series_row.preview_deface_method == "deface_failed_runtime"
        assert series_row.preview_generated_at is None

        frames = session.scalars(
            select(DicomPreviewFrame).where(
                DicomPreviewFrame.pseudo_series_uid == pseudo_series_uid
            )
        ).all()
        assert frames == []

        audits = session.scalars(
            select(PhiScrubAudit).where(
                PhiScrubAudit.pseudo_series_uid == pseudo_series_uid
            )
        ).all()
        assert len(audits) == 1
        a = audits[0]
        assert a.outcome == "quarantine_runtime"
        assert a.error_code == "AFNI_CRASH"
        # error_detail "afni dumped core" has no digit run -> preserved
        assert a.error_detail == "afni dumped core"


def test_ingest_with_preview_skipped_block_is_noop(built_app):
    """``manifest.preview = {skipped: true}`` (gateway flag-off) →
    series.preview_status stays at default 'pending', no frame rows,
    no audit rows."""
    client, token, factory = built_app
    files = [("0001.dcm", b"d-1")]
    pseudo_study_uid = "2.25.pp.skipped"
    pseudo_series_uid = f"{pseudo_study_uid}.s1"

    preview_block = {
        "skipped": True,
        "reason": "flag_off",
        "pipeline_version": "0.1.0",
        "series": [],
    }

    manifest = _build_manifest_with_preview(
        files,
        pseudo_study_uid=pseudo_study_uid,
        preview_block=preview_block,
    )
    r = _post(client, token, manifest, files, key="01HX-PP-SKIP-00000000000")
    assert r.status_code == 201, r.text

    with factory() as session:
        series_row = session.scalar(
            select(Series).where(Series.pseudo_series_uid == pseudo_series_uid)
        )
        assert series_row.preview_status == "pending"
        assert series_row.preview_frame_count == 0
        assert series_row.preview_deface_method is None

        frames = session.scalars(
            select(DicomPreviewFrame).where(
                DicomPreviewFrame.pseudo_series_uid == pseudo_series_uid
            )
        ).all()
        assert frames == []

        audits = session.scalars(
            select(PhiScrubAudit).where(
                PhiScrubAudit.pseudo_series_uid == pseudo_series_uid
            )
        ).all()
        assert audits == []


def test_ingest_without_preview_block_unchanged(built_app):
    """Pre-jpg-preview-defacing manifest (no preview key) → ingest
    succeeds, series row stays at default 'pending' / 0."""
    client, token, factory = built_app
    files = [("0001.dcm", b"d-1")]
    pseudo_study_uid = "2.25.pp.legacy"
    pseudo_series_uid = f"{pseudo_study_uid}.s1"
    manifest = _build_manifest_with_preview(
        files, pseudo_study_uid=pseudo_study_uid, preview_block=None
    )
    r = _post(client, token, manifest, files, key="01HX-PP-LEGACY-000000000")
    assert r.status_code == 201, r.text

    with factory() as session:
        series_row = session.scalar(
            select(Series).where(Series.pseudo_series_uid == pseudo_series_uid)
        )
        assert series_row.preview_status == "pending"
        assert series_row.preview_frame_count == 0
        frames = session.scalars(select(DicomPreviewFrame)).all()
        assert frames == []
        audits = session.scalars(select(PhiScrubAudit)).all()
        assert audits == []


def test_ingest_phi_guard_redacts_long_digit_runs(built_app):
    """HIGH #5 — error_detail with a long digit run gets replaced with
    'redacted_by_phi_guard'."""
    client, token, factory = built_app
    files = [("0001.dcm", b"d-1")]
    pseudo_study_uid = "2.25.pp.phi.guard"
    pseudo_series_uid = f"{pseudo_study_uid}.s1"

    # Imagine a future bad-actor commit that emits patient identifier
    # in error_detail. The guard must replace it.
    preview_block = {
        "skipped": False,
        "pipeline_version": "0.1.0",
        "series": [
            {
                "pseudo_series_uid": pseudo_series_uid,
                "series_num": 1,
                "modality": "MR",
                "body_part": "BRAIN",
                "preview_status": "quarantined",
                "deface_decision": "required",
                "deface_decision_reason": "BodyPartExamined=BRAIN",
                "phi_scrub_method": "deface_failed_runtime",
                "frame_count": 0,
                "frames": [],
                "duration_ms": 1_000,
                "outcome": "quarantine_runtime",
                "error_code": "AFNI_CRASH",
                # Pretend this leaked an MRN - 7 digits in a row.
                "error_detail": "failed for patient mrn=1234567",
            }
        ],
    }

    manifest = _build_manifest_with_preview(
        files,
        pseudo_study_uid=pseudo_study_uid,
        preview_block=preview_block,
    )
    r = _post(client, token, manifest, files, key="01HX-PP-PHI-000000000000")
    assert r.status_code == 201, r.text

    with factory() as session:
        a = session.scalars(
            select(PhiScrubAudit).where(
                PhiScrubAudit.pseudo_series_uid == pseudo_series_uid
            )
        ).one()
        # The PHI guard replaced the offending string; error_code still
        # gives the diagnostic signal.
        assert a.error_detail == "redacted_by_phi_guard"
        assert a.error_code == "AFNI_CRASH"
