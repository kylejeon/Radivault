"""Order validator — 6 FR-11 checks in order."""

from __future__ import annotations

import pytest

from radivault_fulfillment.config import TierDefaults
from radivault_fulfillment.errors import (
    OrderDuplicateStudy,
    OrderQuotaExceeded,
    OrderScopeForbidden,
    OrderStudyNotFound,
    OrderTierExceeded,
    OrderTooLarge,
)
from radivault_fulfillment.orders.validator import validate_order


def _tier() -> TierDefaults:
    return TierDefaults(
        max_cohort_size=3,
        max_order_bytes=10 * 1024 * 1024,
        daily_order_quota=2,
        download_ttl_max_seconds=86400,
        unit_price_usd=5.0,
    )


def test_duplicate_inside_request_rejected(engine_and_factory, seeded_studies) -> None:
    _, factory = engine_and_factory
    uids = seeded_studies
    with factory() as s:
        with pytest.raises(OrderDuplicateStudy):
            validate_order(
                s,
                buyer_pk=1,
                tier="preview",
                scope_json={},
                tier_cfg=_tier(),
                pseudo_study_uids=[uids[0], uids[0]],
            )


def test_tier_cohort_cap(engine_and_factory, seeded_studies) -> None:
    _, factory = engine_and_factory
    uids = seeded_studies
    with factory() as s:
        with pytest.raises(OrderTierExceeded):
            validate_order(
                s,
                buyer_pk=1,
                tier="preview",
                scope_json={},
                tier_cfg=_tier(),
                pseudo_study_uids=uids[:4],  # cap is 3
            )


def test_study_not_found(engine_and_factory, seeded_studies) -> None:
    _, factory = engine_and_factory
    with factory() as s:
        with pytest.raises(OrderStudyNotFound):
            validate_order(
                s,
                buyer_pk=1,
                tier="preview",
                scope_json={},
                tier_cfg=_tier(),
                pseudo_study_uids=["2.25.nonexistent"],
            )


def test_size_cap(engine_and_factory, seeded_studies) -> None:
    _, factory = engine_and_factory
    uids = seeded_studies
    tier = _tier()
    tier.max_order_bytes = 100  # 100 B — smaller than a single study
    with factory() as s:
        with pytest.raises(OrderTooLarge):
            validate_order(
                s,
                buyer_pk=1,
                tier="preview",
                scope_json={},
                tier_cfg=tier,
                pseudo_study_uids=[uids[0]],
            )


def test_scope_exclude(engine_and_factory, seeded_studies, seeded_hospital) -> None:
    _, factory = engine_and_factory
    uids = seeded_studies
    hosp, _ = seeded_hospital
    with factory() as s:
        with pytest.raises(OrderScopeForbidden):
            validate_order(
                s,
                buyer_pk=1,
                tier="preview",
                scope_json={"exclude_hospitals": [hosp.hospital_pk]},
                tier_cfg=_tier(),
                pseudo_study_uids=[uids[0]],
            )


def test_daily_quota(engine_and_factory, seeded_studies, seeded_buyer) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from radivault_fulfillment.db.models import Order

    _, factory = engine_and_factory
    uids = seeded_studies
    buyer, _ = seeded_buyer
    # Pre-seed 2 existing orders for this buyer (quota=2).
    with factory() as s:
        for i in range(2):
            s.add(
                Order(
                    order_id=f"ord_quota_{i}",
                    buyer_pk=buyer.buyer_pk,
                    kid="k" * 8,
                    status="queued",
                    n_studies=1,
                    total_bytes=100,
                    total_estimated_usd=Decimal("5.00"),
                    tier="preview",
                    agreement_hash="0" * 64,
                    submitted_at=datetime.now(tz=UTC),
                )
            )
        s.commit()
    with factory() as s:
        with pytest.raises(OrderQuotaExceeded):
            validate_order(
                s,
                buyer_pk=buyer.buyer_pk,
                tier="preview",
                scope_json={},
                tier_cfg=_tier(),
                pseudo_study_uids=[uids[0]],
            )


def test_happy_path_partitions_hot_cold(engine_and_factory, seeded_studies, seeded_buyer) -> None:
    """All seed studies have central_object_present=False → all cold."""
    _, factory = engine_and_factory
    uids = seeded_studies
    buyer, _ = seeded_buyer
    with factory() as s:
        cohort = validate_order(
            s,
            buyer_pk=buyer.buyer_pk,
            tier="preview",
            scope_json={},
            tier_cfg=_tier(),
            pseudo_study_uids=uids[:2],
        )
    assert cohort.path_type == "cold"
    assert cohort.hot_hit == set()
    assert cohort.cold == set(uids[:2])
    assert cohort.total_bytes == 2 * 512 * 1024
