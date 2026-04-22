"""Anchor chain validator + insert helper (dev-spec §4.2, §8.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.orm import Session

from radivault_central.db.models import AuditAnchor
from radivault_central.db.repository import latest_anchor
from radivault_central.errors import (
    AnchorDuplicate,
    AnchorHashDuplicate,
    AnchorInitial,
    AnchorMono,
    AnchorOrder,
    AnchorRange,
)


def _as_utc(dt: datetime) -> datetime:
    """Normalise naive/aware datetimes to aware UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@dataclass
class AnchorChainReport:
    hospital_pk: int
    anchors: int
    seq_lo: int | None
    seq_hi: int | None
    continuity_ok: bool
    monotonic_ok: bool
    last_anchored_at: datetime | None
    first_break_at: int | None = None


def insert_anchor(
    session: Session,
    *,
    hospital_pk: int,
    gateway_id: str,
    seq_lo: int,
    seq_hi: int,
    head_hash: bytes,
    anchored_at: datetime,
) -> AuditAnchor:
    """Verify chain rules, insert, and return the new row."""
    if seq_lo > seq_hi:
        raise AnchorOrder(detail=f"seq_lo={seq_lo} > seq_hi={seq_hi}")

    # Duplicate checks first so retries hit 409 before a 400 chain-continuity
    # error. Dev-spec §8.2 shows the DB constraint catching these at INSERT;
    # we model the same ordering explicitly.
    dup_range = session.scalar(
        select(AuditAnchor).where(
            AuditAnchor.hospital_pk == hospital_pk,
            AuditAnchor.seq_lo == seq_lo,
            AuditAnchor.seq_hi == seq_hi,
        )
    )
    if dup_range is not None:
        raise AnchorDuplicate()

    dup_hash = session.scalar(
        select(AuditAnchor).where(
            AuditAnchor.hospital_pk == hospital_pk,
            AuditAnchor.head_hash == head_hash,
        )
    )
    if dup_hash is not None:
        raise AnchorHashDuplicate()

    prev = latest_anchor(session, hospital_pk)
    if prev is None:
        if seq_lo != 1:
            raise AnchorInitial(detail=f"first anchor seq_lo={seq_lo} (expected 1)")
    else:
        if seq_lo != prev.seq_hi + 1:
            raise AnchorRange(
                detail=(
                    f"seq_lo={seq_lo} but prev.seq_hi={prev.seq_hi} "
                    f"(expected next {prev.seq_hi + 1})"
                )
            )
        if _as_utc(anchored_at) <= _as_utc(prev.anchored_at):
            raise AnchorMono(
                detail=(
                    f"anchored_at={anchored_at.isoformat()} not > "
                    f"prev.anchored_at={prev.anchored_at.isoformat()}"
                )
            )

    row = AuditAnchor(
        hospital_pk=hospital_pk,
        gateway_id=gateway_id,
        seq_lo=seq_lo,
        seq_hi=seq_hi,
        head_hash=head_hash,
        anchored_at=anchored_at,
    )
    session.add(row)
    session.flush()
    return row


def verify_chain(
    session: Session,
    *,
    hospital_pk: int,
    seq_from: int | None = None,
    seq_to: int | None = None,
) -> AnchorChainReport:
    """Walk the anchor chain and report whether it is unbroken."""
    query = (
        select(AuditAnchor)
        .where(AuditAnchor.hospital_pk == hospital_pk)
        .order_by(AuditAnchor.seq_lo.asc())
    )
    rows = list(session.scalars(query).all())
    if seq_from is not None:
        rows = [r for r in rows if r.seq_lo >= seq_from]
    if seq_to is not None:
        rows = [r for r in rows if r.seq_hi <= seq_to]

    if not rows:
        return AnchorChainReport(
            hospital_pk=hospital_pk,
            anchors=0,
            seq_lo=None,
            seq_hi=None,
            continuity_ok=True,
            monotonic_ok=True,
            last_anchored_at=None,
        )

    continuity_ok = True
    monotonic_ok = True
    first_break: int | None = None
    for prev, cur in pairwise(rows):
        if cur.seq_lo != prev.seq_hi + 1:
            continuity_ok = False
            if first_break is None:
                first_break = cur.seq_lo
        if _as_utc(cur.anchored_at) <= _as_utc(prev.anchored_at):
            monotonic_ok = False

    return AnchorChainReport(
        hospital_pk=hospital_pk,
        anchors=len(rows),
        seq_lo=rows[0].seq_lo,
        seq_hi=rows[-1].seq_hi,
        continuity_ok=continuity_ok,
        monotonic_ok=monotonic_ok,
        last_anchored_at=rows[-1].anchored_at,
        first_break_at=first_break,
    )
