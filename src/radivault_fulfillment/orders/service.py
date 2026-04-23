"""Order lifecycle orchestration (dev-spec §8.1).

Builds the initial ``order`` + ``order_item`` + ``order_outbox`` + history
rows in a single transaction. Hot-Storage partition is already computed
by :func:`radivault_fulfillment.orders.validator.validate_order`; this
module simply translates it into rows.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session
from ulid import ULID

from radivault_central.db.models import Hospital, Study
from radivault_fulfillment.config import Settings, TierDefaults
from radivault_fulfillment.db.models import (
    Order,
    OrderItem,
    OrderOutbox,
    OrderStateHistory,
)
from radivault_fulfillment.orders.pricing import estimate_order_price
from radivault_fulfillment.orders.validator import ValidatedCohort

log = logging.getLogger("radivault_fulfillment.orders.service")


RULESET_VERSION = "v0.1.0"
SALT_VERSION = 1


def _order_id() -> str:
    return f"ord_{ULID()!s}"


def _transfer_job_id() -> str:
    return f"tj_{ULID()!s}"


def _estimated_ready_at(
    *, submitted_at: datetime, cohort: ValidatedCohort, settings: Settings
) -> datetime:
    """Linear heuristic (dev-spec §8.1)."""
    seconds = (
        len(cohort.hot_hit) * settings.order.estimated_ready_seconds_per_study_hot
        + len(cohort.cold) * settings.order.estimated_ready_seconds_per_study_cold
    )
    return submitted_at + timedelta(seconds=seconds)


def create_order(
    session: Session,
    *,
    buyer_pk: int,
    kid: str,
    tier: str,
    tier_cfg: TierDefaults,
    cohort: ValidatedCohort,
    agreement_hash: str,
    notes: str | None,
    settings: Settings,
) -> tuple[Order, list[OrderItem]]:
    """Insert order + items + queue_transfer_jobs outbox event (FR-13)."""
    now = datetime.now(tz=UTC)
    order_id = _order_id()
    path_type = cohort.path_type
    total_usd = estimate_order_price(tier_cfg, n_studies=len(cohort.studies))

    order = Order(
        order_id=order_id,
        buyer_pk=buyer_pk,
        kid=kid,
        status="queued",
        status_billing="pending_billing",
        n_studies=len(cohort.studies),
        total_bytes=cohort.total_bytes,
        total_estimated_usd=total_usd,
        tier=tier,
        agreement_hash=agreement_hash,
        path_type=path_type,
        notes=notes,
        submitted_at=now,
        validated_at=now,
        queued_at=now,
    )
    session.add(order)
    session.flush()

    items: list[OrderItem] = []
    for study in cohort.studies:
        is_hot = study.pseudo_study_uid in cohort.hot_hit
        item = OrderItem(
            order_pk=order.order_pk,
            pseudo_study_uid=study.pseudo_study_uid,
            hospital_pk=study.hospital_pk,
            source="hot_storage" if is_hot else "on_demand",
            state="hot_hit_pending_copy" if is_hot else "pending",
            n_instances=study.n_instances,
            total_bytes=study.total_bytes,
        )
        session.add(item)
        items.append(item)

    # Outbox event: poller will fan out transfer_jobs per hospital_pk.
    # For the all-hot path the poller short-circuits to staging_copy.
    session.add(
        OrderOutbox(
            order_pk=order.order_pk,
            event_type="order.queue_transfer_jobs",
            payload={
                "order_pk": order.order_pk,
                "order_id": order.order_id,
                "path_type": path_type,
                "hospital_groups": _group_by_hospital(cohort),
                "ruleset_version_required": RULESET_VERSION,
                "salt_version_required": SALT_VERSION,
            },
        )
    )
    session.add(
        OrderStateHistory(
            order_pk=order.order_pk,
            from_state=None,
            to_state="queued",
            event="order.created",
            actor="buyer",
            actor_ref=str(buyer_pk),
        )
    )

    estimated_ready_at = _estimated_ready_at(
        submitted_at=now, cohort=cohort, settings=settings
    )
    # ETA written to `expires_at`? No — dev-spec keeps expires_at null until ready.
    # We return the estimate via response only.
    log.info(
        "order_created",
        extra={
            "event": "order.created",
            "order_id": order.order_id,
            "buyer_pk": buyer_pk,
            "tier": tier,
            "path_type": path_type,
            "n_studies": len(cohort.studies),
            "estimated_ready_at": estimated_ready_at.isoformat(),
        },
    )
    return order, items


def _group_by_hospital(cohort: ValidatedCohort) -> list[dict[str, Any]]:
    """Group the cold subset by hospital_pk for transfer_job fan-out."""
    grouped: dict[int, list[dict[str, Any]]] = {}
    for study in cohort.studies:
        if study.pseudo_study_uid in cohort.hot_hit:
            continue  # hot → staging_copy path
        grouped.setdefault(study.hospital_pk, []).append(
            {
                "pseudo_study_uid": study.pseudo_study_uid,
                "expected_instances": study.n_instances,
                "priority": 1,
            }
        )
    return [
        {"hospital_pk": hp, "studies": entries} for hp, entries in grouped.items()
    ]


def compute_estimated_ready_at(
    *, submitted_at: datetime, hot: int, cold: int, settings: Settings
) -> datetime:
    return submitted_at + timedelta(
        seconds=hot * settings.order.estimated_ready_seconds_per_study_hot
        + cold * settings.order.estimated_ready_seconds_per_study_cold
    )


__all__ = [
    "RULESET_VERSION",
    "SALT_VERSION",
    "compute_estimated_ready_at",
    "create_order",
]
