"""Facet aggregation unit tests (FR-31..FR-34)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from radivault_central.db.models import Base as CentralBase
from radivault_central.db.models import Hospital, PatientPseudo, Study
from radivault_search.db.session import get_engine, reset_for_tests
from radivault_search.query.facets import compute_facets


@pytest.fixture
def seeded():
    reset_for_tests()
    engine = get_engine("sqlite+pysqlite:///:memory:", pool_size=1, max_overflow=0)
    CentralBase.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        h = Hospital(hospital_id="h", name="h", salt_version_current=1, allowed_ruleset_versions=[])
        session.add(h)
        session.flush()
        pp = PatientPseudo(
            hospital_pk=h.hospital_pk, pseudo_patient_key="p1", age_bucket=60, sex="M"
        )
        session.add(pp)
        session.flush()
        mods = ["CT"] * 3 + ["MR"] * 2 + ["CR"]
        for i, m in enumerate(mods):
            session.add(
                Study(
                    pseudo_study_uid=f"u_{i}",
                    hospital_pk=h.hospital_pk,
                    patient_pseudo_pk=pp.patient_pseudo_pk,
                    modality=m,
                    body_part="CHEST",
                    manufacturer="SIEMENS",
                    study_date_shifted=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
                    n_instances=1,
                    n_series=1,
                    total_bytes=1,
                    central_job_id="j",
                    gateway_id="gw",
                )
            )
        session.commit()
        yield session
    engine.dispose()
    reset_for_tests()


def test_facet_counts(seeded) -> None:
    facets = compute_facets(seeded, where_clauses=[], dialect="sqlite")
    mod_counts = {f.value: f.count for f in facets["modality"]}
    assert mod_counts["CT"] == 3
    assert mod_counts["MR"] == 2
    assert mod_counts["CR"] == 1
    # sorted count DESC
    assert facets["modality"][0].value == "CT"


def test_facet_sex_and_age(seeded) -> None:
    facets = compute_facets(seeded, where_clauses=[], dialect="sqlite")
    sex_values = {f.value for f in facets["sex"]}
    assert "M" in sex_values
    age_values = {f.value for f in facets["age_bucket"]}
    assert "60" in age_values
