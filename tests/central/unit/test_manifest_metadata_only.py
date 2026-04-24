"""Unit tests for the metadata-only manifest validator branch.

Covers ``ManifestValidator.parse_and_validate_metadata_only`` — the Flow A
entry point that accepts an empty ``files`` array + ``n_instances == 0`` but
still enforces every other business rule (anonymization flag, ruleset
allowlist, salt version, DICOM method code, hospital limits).
"""

from __future__ import annotations

import json

import pytest

from radivault_central.db.models import Hospital
from radivault_central.errors import (
    ManifestAnon,
    ManifestDeid,
    ManifestRuleset,
    ManifestSalt,
    ManifestSchema,
    ManifestTooMany,
)
from radivault_central.manifest.schema import ManifestMetadataOnly
from radivault_central.manifest.validator import ManifestValidator


def _hospital(**overrides) -> Hospital:
    hospital = Hospital(
        hospital_id="hosp_test",
        name="Test Hospital",
        salt_version_current=1,
        allowed_ruleset_versions=["v0.1.0"],
        max_instances_per_study=5000,
        max_study_bytes=20 * 1024 * 1024,
    )
    for k, v in overrides.items():
        setattr(hospital, k, v)
    return hospital


def _metadata_manifest(**overrides) -> dict:
    base = {
        "manifest_version": 1,
        "gateway_id": "gw_test",
        "hospital_id": "hosp_test",
        "pseudo_study_uid": "2.25.meta.1",
        "modalities": ["MR"],
        "n_instances": 42,
        "total_bytes": 123456,
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt_version": 1,
            "method_code_sequence": ["113100"],
        },
        "anonymization_flag": "fully_anonymized",
        "files": [],
        "generated_at": "2026-04-24T10:00:00Z",
    }
    base.update(overrides)
    return base


def _raw(m: dict) -> bytes:
    return json.dumps(m).encode()


def test_metadata_only_empty_files_accepted():
    v = ManifestValidator(_hospital())
    m = v.parse_and_validate_metadata_only(_raw(_metadata_manifest()))
    assert isinstance(m, ManifestMetadataOnly)
    assert m.files == []
    assert m.n_instances == 42
    assert m.total_bytes == 123456


def test_metadata_only_zero_instances_accepted():
    """n_instances=0 is allowed (Gateway may have filtered to empty study)."""
    v = ManifestValidator(_hospital())
    m = v.parse_and_validate_metadata_only(
        _raw(_metadata_manifest(n_instances=0, total_bytes=0))
    )
    assert m.n_instances == 0


def test_metadata_only_rejects_wrong_anonymization_flag():
    """D-3 gate still applies even when files are absent."""
    v = ManifestValidator(_hospital())
    with pytest.raises(ManifestAnon):
        v.parse_and_validate_metadata_only(
            _raw(_metadata_manifest(anonymization_flag="partial"))
        )


def test_metadata_only_rejects_wrong_ruleset():
    v = ManifestValidator(_hospital(allowed_ruleset_versions=["v0.2.0"]))
    with pytest.raises(ManifestRuleset):
        v.parse_and_validate_metadata_only(_raw(_metadata_manifest()))


def test_metadata_only_rejects_wrong_salt_version():
    v = ManifestValidator(_hospital(salt_version_current=3))
    with pytest.raises(ManifestSalt):
        v.parse_and_validate_metadata_only(_raw(_metadata_manifest()))


def test_metadata_only_rejects_missing_113100():
    v = ManifestValidator(_hospital())
    m = _metadata_manifest()
    m["deid"]["method_code_sequence"] = ["113107"]
    with pytest.raises(ManifestDeid):
        v.parse_and_validate_metadata_only(_raw(m))


def test_metadata_only_enforces_hospital_limits():
    v = ManifestValidator(_hospital(max_instances_per_study=100))
    with pytest.raises(ManifestTooMany):
        v.parse_and_validate_metadata_only(_raw(_metadata_manifest(n_instances=500)))


def test_metadata_only_rejects_empty_body():
    v = ManifestValidator(_hospital())
    with pytest.raises(ManifestSchema):
        v.parse_and_validate_metadata_only(b"")


def test_metadata_only_rejects_malformed_json():
    v = ManifestValidator(_hospital())
    with pytest.raises(ManifestSchema):
        v.parse_and_validate_metadata_only(b"{not json}")


def test_metadata_only_rejects_missing_field():
    v = ManifestValidator(_hospital())
    m = _metadata_manifest()
    m.pop("pseudo_study_uid")
    with pytest.raises(ManifestSchema):
        v.parse_and_validate_metadata_only(_raw(m))
