"""Manifest preflight validation (FR-34..FR-41)."""

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
    ManifestTooBig,
    ManifestTooMany,
    ManifestVersion,
)
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


def _manifest(**overrides) -> dict:
    base = {
        "manifest_version": 1,
        "gateway_id": "gw_test",
        "hospital_id": "hosp_test",
        "pseudo_study_uid": "2.25.abc",
        "modalities": ["MR"],
        "n_instances": 1,
        "total_bytes": 12,
        "deid": {
            "ruleset_version": "v0.1.0",
            "salt_version": 1,
            "method_code_sequence": ["113100"],
        },
        "anonymization_flag": "fully_anonymized",
        "files": [
            {"filename": "0001.dcm", "sha256": "a" * 64, "bytes": 12},
        ],
        "generated_at": "2026-04-22T10:00:00Z",
    }
    base.update(overrides)
    return base


def _raw(m: dict) -> bytes:
    return json.dumps(m).encode()


def test_valid_manifest_passes():
    v = ManifestValidator(_hospital())
    manifest = v.parse_and_validate(_raw(_manifest()))
    assert manifest.pseudo_study_uid == "2.25.abc"
    assert manifest.anonymization_flag == "fully_anonymized"


def test_manifest_version_rejected():
    v = ManifestValidator(_hospital())
    with pytest.raises(ManifestVersion):
        v.parse_and_validate(_raw(_manifest(manifest_version=2)))


def test_manifest_bad_anonymization_flag():
    v = ManifestValidator(_hospital())
    with pytest.raises(ManifestAnon):
        v.parse_and_validate(_raw(_manifest(anonymization_flag="pseudonymized")))


def test_manifest_ruleset_allowlist():
    v = ManifestValidator(_hospital(allowed_ruleset_versions=["v0.1.0"]))
    m = _manifest()
    m["deid"]["ruleset_version"] = "v9.9.9"
    with pytest.raises(ManifestRuleset):
        v.parse_and_validate(_raw(m))


def test_manifest_salt_mismatch():
    v = ManifestValidator(_hospital(salt_version_current=7))
    with pytest.raises(ManifestSalt):
        v.parse_and_validate(_raw(_manifest()))


def test_manifest_missing_deid_code():
    v = ManifestValidator(_hospital())
    m = _manifest()
    m["deid"]["method_code_sequence"] = ["999999"]
    with pytest.raises(ManifestDeid):
        v.parse_and_validate(_raw(m))


def test_manifest_toomany_instances():
    v = ManifestValidator(_hospital(max_instances_per_study=2))
    with pytest.raises(ManifestTooMany):
        v.parse_and_validate(_raw(_manifest(n_instances=10)))


def test_manifest_toobig_bytes():
    v = ManifestValidator(_hospital(max_study_bytes=8))
    with pytest.raises(ManifestTooBig):
        v.parse_and_validate(_raw(_manifest(total_bytes=16)))


def test_manifest_schema_error_on_bad_json():
    v = ManifestValidator(_hospital())
    with pytest.raises(ManifestSchema):
        v.parse_and_validate(b"{invalid]")
