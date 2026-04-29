"""Manifest v2 acceptance — metadata-thumbnail-ingest FR-META-1."""

from __future__ import annotations

import base64
import json

import pytest

from radivault_central.db.models import Hospital
from radivault_central.manifest.validator import ManifestValidator


def _hospital() -> Hospital:
    return Hospital(
        hospital_id="hosp_v2",
        name="V2 Hospital",
        salt_version_current=1,
        allowed_ruleset_versions=["v0.1.0"],
        max_instances_per_study=5000,
        max_study_bytes=20 * 1024 * 1024,
    )


def _manifest_v2(**overrides) -> dict:
    base = {
        "manifest_version": 2,
        "gateway_id": "gw_test",
        "hospital_id": "hosp_v2",
        "pseudo_study_uid": "2.25.v2.abc",
        "modalities": ["CT"],
        "n_instances": 3,
        "total_bytes": 1234,
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
        "files": [
            {"filename": "a.dcm", "sha256": "a" * 64, "bytes": 100},
            {"filename": "b.dcm", "sha256": "b" * 64, "bytes": 200},
            {"filename": "c.dcm", "sha256": "c" * 64, "bytes": 300},
        ],
        "generated_at": "2026-04-25T00:00:00Z",
        # v2 fields
        "body_part_examined": "CHEST",
        "patient_sex": "M",
        "patient_age_bucket": "55-59",
        "manufacturer": "GE Medical Systems",
        "manufacturer_model_name": "Revolution CT",
        "study_date_shifted": "2024-03-15",
        "study_year": 2024,
        "n_series": 1,
        "series": [
            {
                "pseudo_series_uid": "2.25.v2.abc.1",
                "modality": "CT",
                "n_instances": 3,
                "body_part": "CHEST",
                "slice_thickness_mm": 1.25,
                "kvp": 120.0,
            }
        ],
        "thumbnail": {
            "sha256": "0" * 64,
            "bytes": 18,
            "format": "JPEG",
            "width": 256,
            "height": 192,
            "source_instance_uid_pseudo": "2.25.v2.abc.1.2",
            "slice_index": 1,
            "slice_count": 3,
            "phi_scrub_status": "passed",
            "phi_scrub_method": "burned_in_tag_gate",
            "data_b64": base64.b64encode(b"\xff\xd8\xff\xe0fake-jpeg-payload").decode(),
        },
    }
    base.update(overrides)
    return base


def test_v2_manifest_round_trip() -> None:
    raw = json.dumps(_manifest_v2()).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    assert m.manifest_version == 2
    assert m.body_part_examined == "CHEST"
    assert m.patient_sex == "M"
    assert m.patient_age_bucket == "55-59"
    assert m.manufacturer == "GE Medical Systems"
    assert m.manufacturer_model_name == "Revolution CT"
    assert m.study_date_shifted == "2024-03-15"
    assert m.study_year == 2024
    assert m.thumbnail is not None
    assert m.thumbnail.phi_scrub_status == "passed"
    assert m.thumbnail.bytes > 0
    assert len(m.series) == 1
    assert m.series[0].modality == "CT"
    assert m.series[0].slice_thickness_mm == 1.25


def test_v1_manifest_still_accepted() -> None:
    """Backward-compat: v1 manifests must still pass."""
    payload = _manifest_v2(manifest_version=1)
    # Strip v2-only fields to simulate a true v1 caller.
    for key in (
        "body_part_examined",
        "patient_sex",
        "patient_age_bucket",
        "manufacturer",
        "manufacturer_model_name",
        "study_date_shifted",
        "study_year",
        "n_series",
        "series",
        "thumbnail",
    ):
        payload.pop(key, None)
    raw = json.dumps(payload).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    assert m.manifest_version == 1
    assert m.body_part_examined is None
    assert m.thumbnail is None
    assert m.series == []


def test_v3_manifest_accepted() -> None:
    """dev-spec-pixel-spatial-fields FR-PSF-4.1 — v3 is accepted."""
    payload = _manifest_v2(manifest_version=3)
    raw = json.dumps(payload).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    assert m.manifest_version == 3


def test_v4_manifest_rejected() -> None:
    """Higher versions than v3 are still rejected."""
    from radivault_central.errors import ManifestVersion

    payload = _manifest_v2(manifest_version=4)
    raw = json.dumps(payload).encode("utf-8")
    validator = ManifestValidator(_hospital())
    with pytest.raises(ManifestVersion):
        validator.parse_and_validate(raw)


def test_thumbnail_b64_payload_decodes() -> None:
    raw = json.dumps(_manifest_v2()).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    decoded = base64.b64decode(m.thumbnail.data_b64)
    assert decoded.startswith(b"\xff\xd8\xff")
