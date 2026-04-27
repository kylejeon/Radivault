"""buyer-search-v3 FR-V3-DATA-2 — manifest.kcd_* round-trip through the
ingest router into the study row.

Regression coverage for the 3-piece wiring gap fixed in this commit:
gateway build_manifest → manifest schema attribute access → router kwarg
into insert_study_full(). Prior to the fix, all new ingests landed with
study.kcd_code IS NULL even when the gateway sent a heuristic value.

Reuses the in-process FastAPI app fixture from test_ingest_e2e.py to avoid
docker-compose dependencies."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

# Reuse the proven fixture from the sibling module.
from tests.central.integration.test_ingest_e2e import built_app  # noqa: F401

from radivault_central.db.models import Study


def _kcd_manifest(
    files: list[tuple[str, bytes]],
    *,
    pseudo_study_uid: str,
    kcd_code: str | None,
    kcd_label_ko: str | None,
    kcd_label_en: str | None,
    include_kcd_keys: bool = True,
) -> dict:
    """Build a v2 manifest carrying (or omitting) KCD heuristic fields."""
    files_meta = [
        {"filename": n, "sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d)}
        for n, d in files
    ]
    manifest: dict = {
        "manifest_version": 2,
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
        "generated_at": "2026-04-27T00:00:00Z",
        "body_part_examined": "CHEST",
        "patient_sex": "M",
        "patient_age_bucket": "55-59",
        "manufacturer": "GE Medical Systems",
        "manufacturer_model_name": "Revolution CT",
        "study_year": 2024,
        "n_series": 1,
        "series": [
            {
                "pseudo_series_uid": f"{pseudo_study_uid}.s1",
                "modality": "CT",
                "n_instances": len(files_meta),
                "body_part": "CHEST",
            }
        ],
    }
    if include_kcd_keys:
        manifest["kcd_code"] = kcd_code
        manifest["kcd_label_ko"] = kcd_label_ko
        manifest["kcd_label_en"] = kcd_label_en
    return manifest


def _post(client, token: str, manifest: dict, files: list[tuple[str, bytes]], key: str):
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


def test_ingest_persists_kcd_columns_when_manifest_has_them(built_app):
    """Happy path — gateway-emitted I20.9 must land on study.kcd_code."""
    client, token, session_factory = built_app
    files = [("a.dcm", b"chest-ct-bytes")]
    pseudo = "2.25.kcd.persist.happy"
    manifest = _kcd_manifest(
        files,
        pseudo_study_uid=pseudo,
        kcd_code="I20.9",
        kcd_label_ko="협심증, 상세불명",
        kcd_label_en="Angina pectoris, unspecified",
    )
    r = _post(client, token, manifest, files, key="01HX-KCD-PERSIST-HAPPY-00001")
    assert r.status_code == 201, r.text

    with session_factory() as session:
        study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo))
        assert study is not None
        assert study.kcd_code == "I20.9"
        assert study.kcd_label_ko == "협심증, 상세불명"
        assert study.kcd_label_en == "Angina pectoris, unspecified"


def test_ingest_persists_kcd_default_z00_fallback(built_app):
    """The Z00.0 DEFAULT_ENTRY (no rule match) round-trips end-to-end."""
    client, token, session_factory = built_app
    files = [("a.dcm", b"unknown-bodypart-bytes")]
    pseudo = "2.25.kcd.persist.default"
    manifest = _kcd_manifest(
        files,
        pseudo_study_uid=pseudo,
        kcd_code="Z00.0",
        kcd_label_ko="일반 의학적 검사",
        kcd_label_en="General medical examination",
    )
    r = _post(client, token, manifest, files, key="01HX-KCD-PERSIST-DEFLT-00001")
    assert r.status_code == 201, r.text

    with session_factory() as session:
        study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo))
        assert study is not None
        assert study.kcd_code == "Z00.0"
        assert study.kcd_label_ko == "일반 의학적 검사"
        assert study.kcd_label_en == "General medical examination"


def test_ingest_pre_v3_manifest_without_kcd_persists_null(built_app):
    """Backward compat — pre-v3 gateways that don't emit kcd_* must still
    succeed and land study.kcd_code IS NULL (additive contract)."""
    client, token, session_factory = built_app
    files = [("a.dcm", b"legacy-bytes")]
    pseudo = "2.25.kcd.persist.legacy"
    manifest = _kcd_manifest(
        files,
        pseudo_study_uid=pseudo,
        kcd_code=None,
        kcd_label_ko=None,
        kcd_label_en=None,
        include_kcd_keys=False,  # simulate true pre-v3 gateway
    )
    r = _post(client, token, manifest, files, key="01HX-KCD-PERSIST-LEGAC-00001")
    assert r.status_code == 201, r.text

    with session_factory() as session:
        study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo))
        assert study is not None
        assert study.kcd_code is None
        assert study.kcd_label_ko is None
        assert study.kcd_label_en is None
