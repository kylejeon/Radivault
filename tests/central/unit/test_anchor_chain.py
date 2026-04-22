"""Anchor chain continuity, monotonicity, duplicates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radivault_central.audit.anchor import insert_anchor, verify_chain
from radivault_central.db.models import Base, Hospital
from radivault_central.errors import (
    AnchorDuplicate,
    AnchorHashDuplicate,
    AnchorInitial,
    AnchorMono,
    AnchorOrder,
    AnchorRange,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    h = Hospital(
        hospital_id="hosp_x",
        name="X",
        salt_version_current=1,
        allowed_ruleset_versions=["v0.1.0"],
    )
    session.add(h)
    session.commit()
    session.refresh(h)
    return session, h


def test_first_anchor_must_start_at_one():
    session, h = _session()
    with pytest.raises(AnchorInitial):
        insert_anchor(
            session,
            hospital_pk=h.hospital_pk,
            gateway_id="gw_x",
            seq_lo=5,
            seq_hi=7,
            head_hash=b"a" * 32,
            anchored_at=datetime.now(tz=UTC),
        )


def test_continuity_and_monotonicity():
    session, h = _session()
    ts = datetime.now(tz=UTC)
    insert_anchor(
        session,
        hospital_pk=h.hospital_pk,
        gateway_id="gw_x",
        seq_lo=1,
        seq_hi=10,
        head_hash=b"a" * 32,
        anchored_at=ts,
    )
    session.commit()
    with pytest.raises(AnchorRange):
        insert_anchor(
            session,
            hospital_pk=h.hospital_pk,
            gateway_id="gw_x",
            seq_lo=20,
            seq_hi=30,
            head_hash=b"b" * 32,
            anchored_at=ts + timedelta(hours=1),
        )
    session.rollback()
    with pytest.raises(AnchorMono):
        insert_anchor(
            session,
            hospital_pk=h.hospital_pk,
            gateway_id="gw_x",
            seq_lo=11,
            seq_hi=20,
            head_hash=b"c" * 32,
            anchored_at=ts,  # equal, not strictly greater
        )


def test_duplicate_range_and_hash():
    session, h = _session()
    ts = datetime.now(tz=UTC)
    insert_anchor(
        session,
        hospital_pk=h.hospital_pk,
        gateway_id="gw_x",
        seq_lo=1,
        seq_hi=10,
        head_hash=b"a" * 32,
        anchored_at=ts,
    )
    session.commit()
    with pytest.raises(AnchorDuplicate):
        insert_anchor(
            session,
            hospital_pk=h.hospital_pk,
            gateway_id="gw_x",
            seq_lo=1,
            seq_hi=10,
            head_hash=b"e" * 32,
            anchored_at=ts + timedelta(hours=1),
        )
    session.rollback()
    with pytest.raises(AnchorHashDuplicate):
        insert_anchor(
            session,
            hospital_pk=h.hospital_pk,
            gateway_id="gw_x",
            seq_lo=11,
            seq_hi=20,
            head_hash=b"a" * 32,  # same head as (1,10)
            anchored_at=ts + timedelta(hours=1),
        )


def test_order_violation():
    session, h = _session()
    with pytest.raises(AnchorOrder):
        insert_anchor(
            session,
            hospital_pk=h.hospital_pk,
            gateway_id="gw_x",
            seq_lo=10,
            seq_hi=5,
            head_hash=b"a" * 32,
            anchored_at=datetime.now(tz=UTC),
        )


def test_verify_chain_reports_intact_chain():
    session, h = _session()
    ts = datetime.now(tz=UTC)
    insert_anchor(
        session,
        hospital_pk=h.hospital_pk,
        gateway_id="gw_x",
        seq_lo=1,
        seq_hi=10,
        head_hash=b"a" * 32,
        anchored_at=ts,
    )
    insert_anchor(
        session,
        hospital_pk=h.hospital_pk,
        gateway_id="gw_x",
        seq_lo=11,
        seq_hi=20,
        head_hash=b"b" * 32,
        anchored_at=ts + timedelta(hours=1),
    )
    session.commit()
    report = verify_chain(session, hospital_pk=h.hospital_pk)
    assert report.anchors == 2
    assert report.continuity_ok
    assert report.monotonic_ok
