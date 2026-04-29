"""dev-spec-pixel-spatial-fields FR-PSF-5 — manifest v3 series-level Tier-1
fields round-trip through the ingest router into the ``series`` row.

Covers AC-PSF-3.3 (v3 happy path), AC-PSF-3.4 (v2 backward-compat —
columns stay NULL), and AC-PSF-3.5 (invalid value graceful → NULL via
gateway extract; central treats absent + null identically).

Reuses the in-process FastAPI app fixture from test_ingest_e2e.py.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

# Reuse the proven fixture from the sibling module.
from tests.central.integration.test_ingest_e2e import built_app  # noqa: F401

from radivault_central.db.models import Series, Study


def _v3_manifest(
    files: list[tuple[str, bytes]],
    *,
    pseudo_study_uid: str,
    include_tier1: bool,
    pseudo_series_uid: str | None = None,
) -> dict:
    """Build a v3 (or v2) manifest with one CT series."""
    files_meta = [
        {"filename": n, "sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d)}
        for n, d in files
    ]
    series_uid = pseudo_series_uid or f"{pseudo_study_uid}.s1"
    series_entry: dict = {
        "pseudo_series_uid": series_uid,
        "modality": "CT",
        "n_instances": len(files_meta),
        "body_part": "CHEST",
    }
    if include_tier1:
        series_entry.update(
            {
                "photometric_interpretation": "MONOCHROME2",
                "pixel_spacing_x": 0.7031,
                "pixel_spacing_y": 0.7031,
                "slice_thickness_mm": 0.625,
                "rows": 512,
                "columns": 512,
                "bits_allocated": 16,
                "bits_stored": 12,
                "frame_of_reference_uid_pseudo": "1.2.840.psf.frame.001",
                "kvp": 120.0,
            }
        )
    return {
        "manifest_version": 3 if include_tier1 else 2,
        "gateway_id": "gw_test",
        "hospital_id": "hosp_test",
        "pseudo_study_uid": pseudo_study_uid,
        "modalities": ["CT"],
        "n_instances": len(files_meta),
        "total_bytes": sum(f["bytes"] for f in files_meta),
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt_version": 1,
            "method_code_sequence": [
                "113100",
                "113101",
                "113103",
                "113106",
                "113109",
                "113111",
            ],
        },
        "anonymization_flag": "fully_anonymized",
        "files": files_meta,
        "generated_at": "2026-04-29T00:00:00Z",
        "body_part_examined": "CHEST",
        "patient_sex": "M",
        "patient_age_bucket": "55-59",
        "manufacturer": "GE Medical Systems",
        "manufacturer_model_name": "Revolution CT",
        "study_year": 2024,
        "n_series": 1,
        "series": [series_entry],
    }


def _post(client, token, manifest, files, key):
    payload = [
        ("manifest", ("manifest.json", json.dumps(manifest).encode(), "application/json")),
    ]
    for name, data in files:
        payload.append(("files", (name, data, "application/dicom")))
    return client.post(
        "/v1/ingest/studies",
        files=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )


# ---------------------------------------------------------------------------
# AC-PSF-3.3 — v3 happy path: all Tier-1 columns land in the series row.
# ---------------------------------------------------------------------------


def test_v3_manifest_persists_tier1_columns(built_app):
    client, token, session_factory = built_app
    files = [("a.dcm", b"ct-bytes-001")]
    pseudo = "2.25.psf.v3.happy"
    manifest = _v3_manifest(files, pseudo_study_uid=pseudo, include_tier1=True)
    r = _post(client, token, manifest, files, key="01HX-PSF-V3-HAPPY-00001")
    assert r.status_code == 201, r.text

    with session_factory() as session:
        study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo))
        assert study is not None
        series = list(
            session.scalars(select(Series).where(Series.study_pk == study.study_pk)).all()
        )
        assert len(series) == 1
        s = series[0]
        assert s.photometric_interpretation == "MONOCHROME2"
        # Numeric -> Decimal on Postgres, float on SQLite. Use float() to
        # normalise either dialect.
        assert float(s.pixel_spacing_x) == 0.7031
        assert float(s.pixel_spacing_y) == 0.7031
        assert float(s.slice_thickness_mm) == 0.625
        assert s.rows_count == 512
        assert s.columns_count == 512
        assert s.bits_allocated == 16
        assert s.bits_stored == 12
        assert s.frame_of_reference_uid_pseudo == "1.2.840.psf.frame.001"
        assert float(s.kvp) == 120.0


# ---------------------------------------------------------------------------
# AC-PSF-3.4 — v2 manifest still accepted; new columns stay NULL.
# ---------------------------------------------------------------------------


def test_v2_manifest_leaves_tier1_columns_null(built_app):
    client, token, session_factory = built_app
    files = [("a.dcm", b"ct-bytes-002")]
    pseudo = "2.25.psf.v2.legacy"
    manifest = _v3_manifest(files, pseudo_study_uid=pseudo, include_tier1=False)
    r = _post(client, token, manifest, files, key="01HX-PSF-V2-LEGAC-00001")
    assert r.status_code == 201, r.text

    with session_factory() as session:
        study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo))
        assert study is not None
        series = list(
            session.scalars(select(Series).where(Series.study_pk == study.study_pk)).all()
        )
        assert len(series) == 1
        s = series[0]
        # All Tier-1 columns NULL on a v2 ingest.
        assert s.photometric_interpretation is None
        assert s.pixel_spacing_x is None
        assert s.pixel_spacing_y is None
        assert s.slice_thickness_mm is None
        assert s.rows_count is None
        assert s.columns_count is None
        assert s.bits_allocated is None
        assert s.bits_stored is None
        assert s.frame_of_reference_uid_pseudo is None
        assert s.kvp is None


# ---------------------------------------------------------------------------
# AC-PSF-5.1 — search executor exposes the new fields on study-detail.
# ---------------------------------------------------------------------------


def test_search_study_detail_exposes_tier1(built_app):
    """Round-trip: ingest v3 → search load_study_detail() returns Tier-1."""
    client, token, session_factory = built_app
    files = [("a.dcm", b"ct-bytes-003")]
    pseudo = "2.25.psf.search.detail"
    manifest = _v3_manifest(files, pseudo_study_uid=pseudo, include_tier1=True)
    r = _post(client, token, manifest, files, key="01HX-PSF-SEARCH-DET-00001")
    assert r.status_code == 201, r.text

    from radivault_search.query.executor import load_study_detail

    with session_factory() as session:
        detail = load_study_detail(
            session, pseudo, buyer_pk=999, global_salt="test-salt"
        )
        assert detail.pseudo_study_uid == pseudo
        assert len(detail.series) == 1
        s = detail.series[0]
        assert s.photometric_interpretation == "MONOCHROME2"
        assert s.pixel_spacing_x == 0.7031
        assert s.pixel_spacing_y == 0.7031
        assert s.slice_thickness_mm == 0.625
        assert s.rows == 512
        assert s.columns == 512
        assert s.bits_allocated == 16
        assert s.bits_stored == 12
        assert s.frame_of_reference_uid_pseudo == "1.2.840.psf.frame.001"
        assert s.kvp == 120.0
