"""Server-side order validation (dev-spec FR-11).

Six synchronous checks in order — scope, tier cohort cap, daily quota,
UID existence + no-dup, size cap, hospital access. Pure functions on an
open SQLAlchemy session — the caller wraps in a single transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from radivault_central.db.models import Study
from radivault_fulfillment.config import TierDefaults
from radivault_fulfillment.db.models import Order
from radivault_fulfillment.errors import (
    OrderDuplicateStudy,
    OrderQuotaExceeded,
    OrderScopeForbidden,
    OrderStudyNotFound,
    OrderTierExceeded,
    OrderTooLarge,
)


@dataclass
class ValidatedCohort:
    """Resolved cohort metadata after FR-11 checks pass."""

    studies: list[Study]  # ordered by request position
    hot_hit: set[str]  # pseudo_study_uids present in Hot Storage
    cold: set[str]
    total_bytes: int
    hospital_pks: set[int]

    @property
    def path_type(self) -> str:
        if not self.cold:
            return "hot"
        if not self.hot_hit:
            return "cold"
        return "mixed"


def validate_order(
    session: Session,
    *,
    buyer_pk: int,
    tier: str,
    scope_json: dict,
    tier_cfg: TierDefaults,
    pseudo_study_uids: list[str],
) -> ValidatedCohort:
    """Run FR-11.1..FR-11.6 in order. Raises the first violation.

    Returns a :class:`ValidatedCohort` with hot/cold partition so the
    service can fan out transfer_jobs / staging_copy directly.
    """
    # FR-11.1 duplicate check inside the request itself.
    if len(pseudo_study_uids) != len({*pseudo_study_uids}):
        raise OrderDuplicateStudy()

    # FR-11.2 tier cohort cap (cheap check before any DB hit).
    if len(pseudo_study_uids) > tier_cfg.max_cohort_size:
        raise OrderTierExceeded(
            detail=(
                f"cohort size {len(pseudo_study_uids)} exceeds "
                f"{tier} cap {tier_cfg.max_cohort_size}"
            )
        )

    # FR-11.3 daily quota.
    since = datetime.now(tz=UTC) - timedelta(days=1)
    stmt = select(func.count(Order.order_pk)).where(
        Order.buyer_pk == buyer_pk,
        Order.submitted_at >= since,
    )
    n_today = session.scalar(stmt) or 0
    if n_today >= tier_cfg.daily_order_quota:
        raise OrderQuotaExceeded(
            detail=f"buyer used {n_today}/{tier_cfg.daily_order_quota} orders in 24h"
        )

    # FR-11.4 all pseudo_study_uids exist.
    rows = (
        session.execute(
            select(Study).where(Study.pseudo_study_uid.in_(pseudo_study_uids))
        )
        .scalars()
        .all()
    )
    present = {r.pseudo_study_uid for r in rows}
    missing = [u for u in pseudo_study_uids if u not in present]
    if missing:
        raise OrderStudyNotFound(detail=f"missing: {missing[:5]}")

    # Order the resolved Study rows by request position for downstream stability.
    by_uid = {r.pseudo_study_uid: r for r in rows}
    ordered = [by_uid[u] for u in pseudo_study_uids]

    # FR-11.5 size cap.
    total_bytes = sum(r.total_bytes for r in ordered)
    if total_bytes > tier_cfg.max_order_bytes:
        raise OrderTooLarge(
            detail=(
                f"total {total_bytes} bytes > tier {tier} cap "
                f"{tier_cfg.max_order_bytes}"
            )
        )

    # FR-11.6 scope — exclude + allowed lists.
    hospital_pks = {r.hospital_pk for r in ordered}
    exclude = set(scope_json.get("exclude_hospitals") or [])
    bad_excl = hospital_pks & exclude
    if bad_excl:
        raise OrderScopeForbidden(
            detail=f"hospital_pks excluded by scope: {sorted(bad_excl)}"
        )
    allowed = scope_json.get("allowed_hospitals")
    if allowed is not None:
        allowed_set = set(allowed)
        bad_allow = hospital_pks - allowed_set
        if bad_allow:
            raise OrderScopeForbidden(
                detail=f"hospital_pks outside allowed scope: {sorted(bad_allow)}"
            )

    # Hot Storage partition (read-only sample of the central_object_present
    # column; FR-34).
    hot_hit = {r.pseudo_study_uid for r in ordered if bool(r.central_object_present)}
    cold = {u for u in pseudo_study_uids if u not in hot_hit}

    return ValidatedCohort(
        studies=ordered,
        hot_hit=hot_hit,
        cold=cold,
        total_bytes=total_bytes,
        hospital_pks=hospital_pks,
    )


__all__ = ["ValidatedCohort", "validate_order"]


# --- Light filter helper used by the FSM entry points -----------------------
def _unused() -> None:
    _ = and_  # keep import for future AND composition if scope needs OR
