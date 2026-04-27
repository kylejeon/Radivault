"""buyer-search-v3 FR-V3-DATA-2 — build_manifest must serialise the
gateway-extracted KCD heuristic fields so central can persist them onto the
study row. Without this, /v1/search/studies KCD filter / facet / sort always
return empty for new ingests (silent failure, no error path).

Companion piece to test_extract_v3_age_kcd.py (which covers the upstream
lookup_kcd) and tests/central/unit/test_manifest_kcd.py (which covers the
manifest schema's kcd_* attribute access)."""

from __future__ import annotations

from pathlib import Path

from radivault_gateway.extract import StudyMetadata
from radivault_gateway.upload import UploadClient


def _make_client() -> UploadClient:
    return UploadClient(
        "http://testserver",
        upload_token="t",
        max_retries=1,
        allow_insecure=True,
    )


def _study_metadata_with_kcd(
    *,
    kcd_code: str | None = "I20.9",
    kcd_label_ko: str | None = "협심증, 상세불명",
    kcd_label_en: str | None = "Angina pectoris, unspecified",
) -> StudyMetadata:
    return StudyMetadata(
        body_part_examined="CHEST",
        patient_sex="M",
        patient_age_bucket="55-59",
        patient_age=57,
        manufacturer="GE Medical Systems",
        manufacturer_model_name="Revolution CT",
        n_series=1,
        series=[{"pseudo_series_uid": "2.25.s1", "modality": "CT", "n_instances": 1}],
        kcd_code=kcd_code,
        kcd_label_ko=kcd_label_ko,
        kcd_label_en=kcd_label_en,
    )


def test_build_manifest_serialises_kcd_when_metadata_present(tmp_path: Path) -> None:
    """Happy path — extract.py populated kcd_* → manifest carries them."""
    f = tmp_path / "a.dcm"
    f.write_bytes(b"alpha")
    client = _make_client()
    try:
        manifest = client.build_manifest(
            gateway_id="gw_x",
            hospital_id="hosp_x",
            pseudo_study_uid="2.25.kcd.happy",
            modalities=["CT"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            dcm_files=[f],
            study_metadata=_study_metadata_with_kcd(),
        )
    finally:
        client.close()
    assert manifest["kcd_code"] == "I20.9"
    assert manifest["kcd_label_ko"] == "협심증, 상세불명"
    assert manifest["kcd_label_en"] == "Angina pectoris, unspecified"


def test_build_manifest_serialises_default_z00_fallback(tmp_path: Path) -> None:
    """When (modality, body_part) has no rule, lookup_kcd returns the Z00.0
    DEFAULT_ENTRY. build_manifest must propagate that, not silently drop it."""
    f = tmp_path / "a.dcm"
    f.write_bytes(b"alpha")
    client = _make_client()
    try:
        manifest = client.build_manifest(
            gateway_id="gw_x",
            hospital_id="hosp_x",
            pseudo_study_uid="2.25.kcd.default",
            modalities=["CT"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            dcm_files=[f],
            study_metadata=_study_metadata_with_kcd(
                kcd_code="Z00.0",
                kcd_label_ko="일반 의학적 검사",
                kcd_label_en="General medical examination",
            ),
        )
    finally:
        client.close()
    assert manifest["kcd_code"] == "Z00.0"
    assert manifest["kcd_label_ko"] == "일반 의학적 검사"
    assert manifest["kcd_label_en"] == "General medical examination"


def test_build_manifest_serialises_kcd_none_when_lookup_failed(tmp_path: Path) -> None:
    """Defensive — if extract somehow set kcd_* to None (e.g. test fixture
    or a non-extract caller), keys must still be present with value None so
    central's Optional schema accepts the manifest unchanged."""
    f = tmp_path / "a.dcm"
    f.write_bytes(b"alpha")
    client = _make_client()
    try:
        manifest = client.build_manifest(
            gateway_id="gw_x",
            hospital_id="hosp_x",
            pseudo_study_uid="2.25.kcd.none",
            modalities=["CT"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            dcm_files=[f],
            study_metadata=_study_metadata_with_kcd(
                kcd_code=None,
                kcd_label_ko=None,
                kcd_label_en=None,
            ),
        )
    finally:
        client.close()
    assert "kcd_code" in manifest
    assert manifest["kcd_code"] is None
    assert manifest["kcd_label_ko"] is None
    assert manifest["kcd_label_en"] is None


def test_build_manifest_v1_no_metadata_omits_kcd(tmp_path: Path) -> None:
    """Backward compat — v1 callers that don't pass study_metadata produce a
    manifest without kcd_* keys (manifest_version=1, additive contract)."""
    f = tmp_path / "a.dcm"
    f.write_bytes(b"alpha")
    client = _make_client()
    try:
        manifest = client.build_manifest(
            gateway_id="gw_x",
            hospital_id="hosp_x",
            pseudo_study_uid="2.25.kcd.v1",
            modalities=["CT"],
            ruleset_version="v0.1.0",
            salt_version=1,
            method_codes=["113100"],
            dcm_files=[f],
            study_metadata=None,
        )
    finally:
        client.close()
    assert manifest["manifest_version"] == 1
    assert "kcd_code" not in manifest
    assert "kcd_label_ko" not in manifest
    assert "kcd_label_en" not in manifest
