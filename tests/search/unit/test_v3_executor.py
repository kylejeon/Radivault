"""buyer-search-v3 FR-V3-API-2/5 — executor returns v3 fields + new sort."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from radivault_central.db.models import Base as CentralBase
from radivault_central.db.models import Hospital, PatientPseudo, Study
from radivault_search.db.session import get_engine, reset_for_tests
from radivault_search.query.executor import run_search
from radivault_search.query.schema import SearchRequest


@pytest.fixture
def session_v3():
    reset_for_tests()
    engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=1, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        h_seoul = Hospital(
            hospital_id="HOSP-001",
            name="Seoul Demo",
            region="KR-SE",
            region_pseudo="SEOUL-A",
            salt_version_current=1,
            allowed_ruleset_versions=[],
        )
        h_busan = Hospital(
            hospital_id="HOSP-002",
            name="Busan Demo",
            region="KR-BS",
            region_pseudo="BUSAN-B",
            salt_version_current=1,
            allowed_ruleset_versions=[],
        )
        session.add_all([h_seoul, h_busan])
        session.flush()
        pp1 = PatientPseudo(
            hospital_pk=h_seoul.hospital_pk,
            pseudo_patient_key="p1",
            sex="F",
            age=52,
            age_bucket=50,
        )
        pp2 = PatientPseudo(
            hospital_pk=h_busan.hospital_pk,
            pseudo_patient_key="p2",
            sex="M",
            age=68,
            age_bucket=65,
        )
        session.add_all([pp1, pp2])
        session.flush()
        session.add(
            Study(
                pseudo_study_uid="s1",
                hospital_pk=h_seoul.hospital_pk,
                patient_pseudo_pk=pp1.patient_pseudo_pk,
                modality="CT",
                body_part="CHEST",
                manufacturer="SIEMENS",
                model_name="SOMATOM Drive",
                kcd_code="I20.9",
                kcd_label_ko="협심증, 상세불명",
                kcd_label_en="Angina pectoris, unspecified",
                study_date_shifted=datetime(2024, 8, 15),
                n_instances=312,
                n_series=3,
                total_bytes=502267904,
                central_job_id="j",
                gateway_id="gw",
            )
        )
        session.add(
            Study(
                pseudo_study_uid="s2",
                hospital_pk=h_busan.hospital_pk,
                patient_pseudo_pk=pp2.patient_pseudo_pk,
                modality="MR",
                body_part="HEAD",
                manufacturer="PHILIPS",
                model_name="Ingenia 3.0T",
                kcd_code="G45.9",
                kcd_label_ko="일과성 뇌허혈 발작",
                kcd_label_en="Transient ischaemic attack",
                study_date_shifted=datetime(2024, 9, 19),
                n_instances=188,
                n_series=5,
                total_bytes=312000000,
                central_job_id="j",
                gateway_id="gw",
            )
        )
        session.commit()
        yield session
    engine.dispose()
    reset_for_tests()


def test_executor_returns_v3_fields(session_v3) -> None:
    req = SearchRequest()
    result = run_search(session_v3, req, buyer_pk=1, global_salt="x")
    assert len(result.response.items) == 2
    item = next(it for it in result.response.items if it.pseudo_study_uid == "s1")
    assert item.patient_age == 52
    assert item.hospital_region_pseudo == "SEOUL-A"
    assert item.kcd_code == "I20.9"
    assert item.kcd_label_ko.startswith("협심증")
    assert item.kcd_label_en.startswith("Angina")


def test_age_min_max_filter(session_v3) -> None:
    req = SearchRequest(age_min=40, age_max=60)
    result = run_search(session_v3, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert "s1" in uids  # age=52
    assert "s2" not in uids  # age=68


def test_kcd_code_filter(session_v3) -> None:
    req = SearchRequest(kcd_code=["I20.9"])
    result = run_search(session_v3, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert uids == ["s1"]


def test_hospital_region_filter(session_v3) -> None:
    req = SearchRequest(hospital_region=["BUSAN-B"])
    result = run_search(session_v3, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert uids == ["s2"]


def test_v3_sort_age_desc(session_v3) -> None:
    req = SearchRequest(sort="age_desc")
    result = run_search(session_v3, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert uids[0] == "s2"  # 68 > 52


def test_v3_sort_size_asc(session_v3) -> None:
    req = SearchRequest(sort="size_asc")
    result = run_search(session_v3, req, buyer_pk=1, global_salt="x")
    uids = [it.pseudo_study_uid for it in result.response.items]
    assert uids[0] == "s2"  # 312M < 502M
