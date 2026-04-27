"""buyer-search-v3 FR-V3-DATA-2 — central manifest schema must declare the
gateway-emitted KCD fields so attribute access (manifest.kcd_code) works in
the ingest router. extra="allow" only retains them inside __pydantic_extra__,
which is a dict — kwarg passing into insert_study_full() requires a real
attribute. Without these declarations, every new ingest persists kcd_code
NULL even when the gateway sent a heuristic value.

Mirrors test_manifest_v2.py for the contract surface."""

from __future__ import annotations

import base64
import json

from radivault_central.db.models import Hospital
from radivault_central.manifest.validator import ManifestValidator


def _hospital() -> Hospital:
    return Hospital(
        hospital_id="hosp_kcd",
        name="KCD Hospital",
        salt_version_current=1,
        allowed_ruleset_versions=["v0.1.0"],
        max_instances_per_study=5000,
        max_study_bytes=20 * 1024 * 1024,
    )


def _manifest_v2_with_kcd(**overrides) -> dict:
    base = {
        "manifest_version": 2,
        "gateway_id": "gw_test",
        "hospital_id": "hosp_kcd",
        "pseudo_study_uid": "2.25.kcd.abc",
        "modalities": ["CT"],
        "n_instances": 1,
        "total_bytes": 100,
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
        ],
        "generated_at": "2026-04-27T00:00:00Z",
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
                "pseudo_series_uid": "2.25.kcd.abc.1",
                "modality": "CT",
                "n_instances": 1,
                "body_part": "CHEST",
            }
        ],
        "thumbnail": {
            "sha256": "0" * 64,
            "bytes": 18,
            "format": "JPEG",
            "width": 256,
            "height": 192,
            "source_instance_uid_pseudo": "2.25.kcd.abc.1.2",
            "slice_index": 0,
            "slice_count": 1,
            "phi_scrub_status": "passed",
            "phi_scrub_method": "burned_in_tag_gate",
            "data_b64": base64.b64encode(b"\xff\xd8\xff\xe0fake-jpeg-payload").decode(),
        },
        # v3 KCD heuristic — populated by gateway extract.py.
        "kcd_code": "I20.9",
        "kcd_label_ko": "협심증, 상세불명",
        "kcd_label_en": "Angina pectoris, unspecified",
    }
    base.update(overrides)
    return base


def test_manifest_parses_kcd_fields_via_attribute_access() -> None:
    """The router does ``manifest.kcd_code`` (attribute, not dict). With
    extra='allow' alone the value lives in __pydantic_extra__ and the
    attribute hand-off would silently coerce to None. Field declaration is
    required for ingest persistence."""
    raw = json.dumps(_manifest_v2_with_kcd()).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    assert m.kcd_code == "I20.9"
    assert m.kcd_label_ko == "협심증, 상세불명"
    assert m.kcd_label_en == "Angina pectoris, unspecified"


def test_manifest_kcd_default_z00_fallback_round_trip() -> None:
    """The DEFAULT_ENTRY (Z00.0) round-trips end-to-end."""
    raw = json.dumps(
        _manifest_v2_with_kcd(
            kcd_code="Z00.0",
            kcd_label_ko="일반 의학적 검사",
            kcd_label_en="General medical examination",
        )
    ).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    assert m.kcd_code == "Z00.0"
    assert m.kcd_label_ko == "일반 의학적 검사"
    assert m.kcd_label_en == "General medical examination"


def test_manifest_without_kcd_is_backward_compat() -> None:
    """Pre-v3 manifests (no kcd_* keys) must still parse with kcd_* = None.
    NFR-TS15-COMPAT-1-style additive guarantee."""
    payload = _manifest_v2_with_kcd()
    payload.pop("kcd_code", None)
    payload.pop("kcd_label_ko", None)
    payload.pop("kcd_label_en", None)
    raw = json.dumps(payload).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    assert m.kcd_code is None
    assert m.kcd_label_ko is None
    assert m.kcd_label_en is None


def test_manifest_kcd_null_explicit_is_accepted() -> None:
    """Gateway may emit explicit JSON null when extract didn't run (Flow A
    metadata-only edge cases). Schema must accept null as valid Optional."""
    raw = json.dumps(
        _manifest_v2_with_kcd(kcd_code=None, kcd_label_ko=None, kcd_label_en=None)
    ).encode("utf-8")
    validator = ManifestValidator(_hospital())
    m = validator.parse_and_validate(raw)
    assert m.kcd_code is None
    assert m.kcd_label_ko is None
    assert m.kcd_label_en is None
