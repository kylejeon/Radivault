"""Hot Storage partition — FR-34/35."""

from __future__ import annotations

from radivault_central.db.models import Study
from radivault_fulfillment.hot_storage.lookup import partition


def test_all_cold(engine_and_factory, seeded_studies) -> None:
    _, factory = engine_and_factory
    uids = seeded_studies
    with factory() as s:
        result = partition(s, pseudo_study_uids=uids)
    assert result.path_type == "cold"
    assert result.cold == set(uids)


def test_all_hot(engine_and_factory, seeded_studies) -> None:
    _, factory = engine_and_factory
    uids = seeded_studies
    with factory() as s:
        s.query(Study).filter(Study.pseudo_study_uid.in_(uids)).update(
            {"central_object_present": True}, synchronize_session=False
        )
        s.commit()
    with factory() as s:
        result = partition(s, pseudo_study_uids=uids)
    assert result.path_type == "hot"
    assert result.hot_hit == set(uids)


def test_mixed(engine_and_factory, seeded_studies) -> None:
    _, factory = engine_and_factory
    uids = seeded_studies
    with factory() as s:
        s.query(Study).filter(Study.pseudo_study_uid == uids[0]).update(
            {"central_object_present": True}, synchronize_session=False
        )
        s.commit()
    with factory() as s:
        result = partition(s, pseudo_study_uids=uids[:3])
    assert result.path_type == "mixed"
    assert result.hot_hit == {uids[0]}
