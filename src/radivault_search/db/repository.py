"""Typed query helpers for radivault_search.

All helpers take an explicit :class:`Session` and are side-effect free (except
:func:`touch_key_last_used` which updates ``last_used_at``). The search service
never writes to ``study``, ``series``, ``instance``, ``hospital``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from radivault_central.db.models import Hospital, Series, Study
from radivault_search.db.models import Buyer, BuyerApiKey, SearchAudit

# ---------------------------------------------------------------------------
# Buyer / key lookups
# ---------------------------------------------------------------------------


def get_key_by_kid(session: Session, kid: str) -> BuyerApiKey | None:
    return session.scalar(select(BuyerApiKey).where(BuyerApiKey.kid == kid))


def get_buyer_by_pk(session: Session, buyer_pk: int) -> Buyer | None:
    return session.get(Buyer, buyer_pk)


def get_buyer_by_id(session: Session, buyer_id: str) -> Buyer | None:
    return session.scalar(select(Buyer).where(Buyer.buyer_id == buyer_id))


def touch_key_last_used(session: Session, key: BuyerApiKey) -> None:
    key.last_used_at = datetime.now(tz=UTC)
    session.commit()


# ---------------------------------------------------------------------------
# Study / Series reads (read-only)
# ---------------------------------------------------------------------------


def get_study_by_pseudo_uid(session: Session, pseudo_study_uid: str) -> Study | None:
    return session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo_study_uid))


def list_series_for_study(session: Session, study_pk: int) -> list[Series]:
    return list(session.scalars(select(Series).where(Series.study_pk == study_pk)).all())


def list_hospitals_with_counts(session: Session) -> list[tuple[int, int, Any, Any]]:
    """Return ``(hospital_pk, study_count, first_date, last_date)`` tuples."""
    stmt = select(
        Study.hospital_pk,
        func.count(Study.study_pk),
        func.min(Study.study_date_shifted),
        func.max(Study.study_date_shifted),
    ).group_by(Study.hospital_pk)
    return [tuple(row) for row in session.execute(stmt).all()]


def list_hospital_rows(session: Session) -> list[Hospital]:
    return list(session.scalars(select(Hospital)).all())


# ---------------------------------------------------------------------------
# Audit append
# ---------------------------------------------------------------------------


def insert_search_audit(
    session: Session,
    *,
    buyer_pk: int,
    kid: str,
    endpoint: str,
    filter_sha256: str | None,
    filter_json_sha256: str | None,
    result_count: int | None,
    cache_hit: bool,
    status_code: int,
    error_code: str | None,
    latency_ms: int,
    request_id: str,
    cursor_presence: bool,
    raw_query: str | None = None,
    masked_query: str | None = None,
    phi_flagged_patterns: list[str] | None = None,
) -> SearchAudit:
    """Append-only insert into ``search_audit``.

    Text-search additions (FR-TS-10): ``raw_query`` is the verbatim buyer
    input (30-day retention via cron), ``masked_query`` is the PHI-scrubbed
    copy (indefinite retention), and ``phi_flagged_patterns`` is a list of
    pattern names that fired during scrub. On Postgres ``phi_flagged_patterns``
    is stored as ``TEXT[]``; on SQLite (tests) it is JSON-encoded text.
    """
    flagged_for_db: list[str] | str | None
    if phi_flagged_patterns is None:
        flagged_for_db = None
    else:
        dialect = session.bind.dialect.name if session.bind is not None else "sqlite"
        if dialect == "postgresql":
            flagged_for_db = list(phi_flagged_patterns)
        else:
            # SQLite — encode as JSON text so the round-trip is loss-free.
            import json as _json

            flagged_for_db = _json.dumps(list(phi_flagged_patterns))

    row = SearchAudit(
        buyer_pk=buyer_pk,
        kid=kid,
        endpoint=endpoint,
        filter_sha256=filter_sha256,
        filter_json_sha256=filter_json_sha256,
        result_count=result_count,
        cache_hit=cache_hit,
        status_code=status_code,
        error_code=error_code,
        latency_ms=latency_ms,
        request_id=request_id,
        cursor_presence=cursor_presence,
        raw_query=raw_query,
        masked_query=masked_query,
        phi_flagged_patterns=flagged_for_db,
    )
    session.add(row)
    session.commit()
    return row
