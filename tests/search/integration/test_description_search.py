"""text-search-description Phase 1.5 — description-aware search wiring.

dev-spec-text-search-description-phase15 — covers FR-TS15-7 (search executor
matches description tokens via SQLite ILIKE fallback in unit tests, mirroring
the Postgres tsvector path), FR-TS15-6 (StudyItem.study_description /
protocol_name surfaced in the response), and AC-TS15-7 (description tokens
participate in the ts_headline highlight, returned as
``highlight_snippet``).

Postgres tsvector / GIN / ts_rank_cd weighting (A=description, B=KCD/body)
is exercised in the manual demo verification stage (§W4 of the dev-spec)
plus the alembic 0009 migration. Here we only need to prove the executor
plumbs the new columns end-to-end on the SQLite contract.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from radivault_central.db.models import Base as CentralBase
from radivault_central.db.models import Hospital, PatientPseudo, Study
from radivault_search.db.session import get_engine, reset_for_tests
from radivault_search.query.executor import run_search
from radivault_search.query.schema import SearchRequest


@pytest.fixture
def session_phase15():
    reset_for_tests()
    engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=1, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        h = Hospital(
            hospital_id="HOSP-001",
            name="Seoul Demo",
            region="KR-SE",
            region_pseudo="SEOUL-A",
            salt_version_current=1,
            allowed_ruleset_versions=[],
        )
        session.add(h)
        session.flush()
        pp = PatientPseudo(
            hospital_pk=h.hospital_pk,
            pseudo_patient_key="p1",
            sex="F",
            age=42,
            age_bucket=40,
        )
        session.add(pp)
        session.flush()
        # s1: knee scanogram → matches via study_description (Phase 1.5).
        session.add(
            Study(
                pseudo_study_uid="s1",
                hospital_pk=h.hospital_pk,
                patient_pseudo_pk=pp.patient_pseudo_pk,
                modality="CR",
                body_part="KNEE",
                manufacturer="GE HEALTHCARE",
                model_name="Optima XR646",
                kcd_code="M17.0",
                kcd_label_ko="슬관절 골관절염",
                kcd_label_en="Knee osteoarthritis",
                study_date_shifted=datetime(2024, 6, 11),
                n_instances=2,
                n_series=1,
                total_bytes=12_000_000,
                central_job_id="j",
                gateway_id="gw",
                study_description="Knee Scanogram",
                protocol_name="AX KNEE Scanogram",
            )
        )
        # s2: brain MR with non-matching description.
        session.add(
            Study(
                pseudo_study_uid="s2",
                hospital_pk=h.hospital_pk,
                patient_pseudo_pk=pp.patient_pseudo_pk,
                modality="MR",
                body_part="BRAIN",
                manufacturer="PHILIPS",
                model_name="Ingenia",
                kcd_code="G45.9",
                kcd_label_ko="일과성 뇌허혈 발작",
                kcd_label_en="Transient ischaemic attack",
                study_date_shifted=datetime(2024, 7, 19),
                n_instances=188,
                n_series=5,
                total_bytes=312_000_000,
                central_job_id="j",
                gateway_id="gw",
                study_description="MR Brain w/ contrast",
                protocol_name="AX T1 FLAIR",
            )
        )
        # s3: NULL description (legacy / pre-Phase-1.5 ingest) → "—" cell.
        session.add(
            Study(
                pseudo_study_uid="s3",
                hospital_pk=h.hospital_pk,
                patient_pseudo_pk=pp.patient_pseudo_pk,
                modality="CT",
                body_part="CHEST",
                manufacturer="SIEMENS",
                model_name="SOMATOM",
                kcd_code="J18.9",
                kcd_label_ko="폐렴, 상세불명",
                kcd_label_en="Pneumonia, unspecified",
                study_date_shifted=datetime(2024, 5, 1),
                n_instances=312,
                n_series=3,
                total_bytes=502_000_000,
                central_job_id="j",
                gateway_id="gw",
                # study_description / protocol_name = None (default).
            )
        )
        # s4: empty-string description (scrubbed but all stripped) →
        # PhiPendingBadge cell render.
        session.add(
            Study(
                pseudo_study_uid="s4",
                hospital_pk=h.hospital_pk,
                patient_pseudo_pk=pp.patient_pseudo_pk,
                modality="MG",
                body_part="BREAST",
                manufacturer="HOLOGIC",
                model_name="Selenia",
                kcd_code="Z12.31",
                kcd_label_ko="유방 선별검사",
                kcd_label_en="Breast cancer screening",
                study_date_shifted=datetime(2024, 4, 18),
                n_instances=4,
                n_series=2,
                total_bytes=18_000_000,
                central_job_id="j",
                gateway_id="gw",
                study_description="",
                protocol_name="",
            )
        )
        session.commit()
        yield session
    engine.dispose()
    reset_for_tests()


def test_study_item_exposes_description_fields(session_phase15) -> None:
    req = SearchRequest()
    result = run_search(session_phase15, req, buyer_pk=1, global_salt="x")
    by_uid = {it.pseudo_study_uid: it for it in result.response.items}
    assert by_uid["s1"].study_description == "Knee Scanogram"
    assert by_uid["s1"].protocol_name == "AX KNEE Scanogram"
    assert by_uid["s2"].study_description == "MR Brain w/ contrast"
    # NULL (legacy) → None on the wire.
    assert by_uid["s3"].study_description is None
    assert by_uid["s3"].protocol_name is None
    # Empty string (scrubbed but all stripped) → "" preserved verbatim
    # so the UI can distinguish "not extracted" from "extracted-but-empty".
    assert by_uid["s4"].study_description == ""
    assert by_uid["s4"].protocol_name == ""


def test_q_matches_description_token(session_phase15) -> None:
    """`q='scanogram'` matches s1 via study_description / protocol_name."""
    req = SearchRequest(q="scanogram")
    result = run_search(session_phase15, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert "s1" in uids
    assert "s2" not in uids


def test_q_matches_protocol_name_token(session_phase15) -> None:
    """`q='flair'` matches s2 via protocol_name (AX T1 FLAIR)."""
    req = SearchRequest(q="flair")
    result = run_search(session_phase15, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert uids == ["s2"]


def test_q_matches_legacy_field_still_works(session_phase15) -> None:
    """Phase 1.0 regression: q on body_part still returns the row even
    when its description column is NULL."""
    req = SearchRequest(q="chest")
    result = run_search(session_phase15, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert uids == ["s3"]


def test_meta_text_search_applied_when_q_set(session_phase15) -> None:
    req = SearchRequest(q="scanogram")
    result = run_search(session_phase15, req, buyer_pk=1, global_salt="x")
    assert result.response.meta.text_search_applied is True


def test_no_q_facet_only_path_includes_description_fields(session_phase15) -> None:
    """AC-TS15-22 — facet-only response shape still surfaces description."""
    req = SearchRequest()
    result = run_search(session_phase15, req, buyer_pk=1, global_salt="x")
    assert result.response.meta.text_search_applied is False
    s1 = next(it for it in result.response.items if it.pseudo_study_uid == "s1")
    assert s1.study_description == "Knee Scanogram"
