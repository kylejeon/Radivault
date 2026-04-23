"""Hospital Dashboard read-only endpoints (dev-spec buyer-portal-demo §7 D-2/D-4).

Three endpoints consumed by the Next.js Hospital Dashboard BFF:

* ``GET /v1/hospital/me/stats`` — aggregate study counts + revenue
  simulation inputs (D-2).
* ``GET /v1/hospital/me/gateway-health`` — last ingest heartbeat + status
  label (D-2, split out for polling cadence).
* ``GET /v1/hospital/me/audit`` — most recent audit events (D-4).

All three are scoped by the hospital bearer token already resolved by
``BearerAuthMiddleware`` — the token maps 1:1 to ``hospital_pk`` so scope
forbidden errors never surface in v0.1 (multi-hospital tokens are v0.2).

PHI posture
-----------
No PHI is materialised in the SELECT projections — only:

* ``hospital_id`` (opaque pseudonym)
* aggregate counts (``COUNT(*)``, ``SUM(total_bytes)``)
* bucket timestamps (``year_month`` strings)
* event_type + ``head_hash[:8]`` + timestamp

Raw DICOM tags (``study.raw_dicom_tags``) are never read.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from radivault_central.auth.middleware import require_hospital
from radivault_central.db.models import AuditIngestEvent, Hospital, Study
from radivault_central.errors import CentralError

log = logging.getLogger("radivault_central.routers.hospital_portal")

router = APIRouter(tags=["hospital-portal"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class MonthlyStudyCount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year_month: str  # "YYYY-MM"
    count: int


class StudyStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    today: int
    cumulative: int
    monthly_12m: list[MonthlyStudyCount]


class GatewayHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["online", "warning", "offline", "unknown"]
    last_sync_at: datetime | None = None
    last_sync_delta_seconds: int | None = None


class ModalityCount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modality: str
    count: int


class StatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hospital_id: str
    studies: StudyStats
    gateway_health: GatewayHealth
    modality_distribution: list[ModalityCount]
    as_of: datetime


class StatsEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: StatsResponse


class GatewayHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hospital_id: str
    gateway_id: str | None = None
    status: Literal["online", "warning", "offline", "unknown"]
    last_sync_at: datetime | None = None
    last_sync_delta_seconds: int | None = None
    as_of: datetime


class GatewayHealthEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: GatewayHealthResponse


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ts: datetime
    event_type: str
    hash_short: str
    detail_code: str | None = None


class AuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hospital_id: str
    events: list[AuditEvent]
    as_of: datetime


class AuditEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: AuditResponse


# ---------------------------------------------------------------------------
# Health helpers
# ---------------------------------------------------------------------------
# Windows per design-spec (last_sync_delta_seconds → status label).
#   < 5 min   → online
#   < 30 min  → warning
#   else      → offline
_ONLINE_THRESHOLD_S = 5 * 60
_WARNING_THRESHOLD_S = 30 * 60


def _health_status(delta_seconds: int | None) -> Literal["online", "warning", "offline", "unknown"]:
    if delta_seconds is None:
        return "unknown"
    if delta_seconds < _ONLINE_THRESHOLD_S:
        return "online"
    if delta_seconds < _WARNING_THRESHOLD_S:
        return "warning"
    return "offline"


def _month_bucket(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _iter_months(end: datetime, n: int) -> list[str]:
    """Return the last ``n`` year_month strings ending with ``end``'s month."""
    year = end.year
    month = end.month
    out: list[str] = []
    for _ in range(n):
        out.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    out.reverse()
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
class _HospitalNotFound(CentralError):
    code = "ERR_HOSPITAL_NOT_FOUND"
    status_code = 404
    message_en = "Hospital row not found for this token."
    message_ko = "토큰에 연결된 병원 정보를 찾을 수 없습니다."


@router.get(
    "/v1/hospital/me/stats",
    response_model=StatsEnvelope,
    summary="Hospital Dashboard — aggregate stats (studies + health + modality)",
)
def get_hospital_stats(
    request: Request,
    period: Literal["today", "30d", "12m"] = Query("12m"),
) -> StatsEnvelope:
    hospital_pk, _ = require_hospital(request)
    session_factory = request.app.state.session_factory

    now = datetime.now(tz=UTC)
    today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)

    with session_factory() as session:
        hospital = session.get(Hospital, hospital_pk)
        if hospital is None:
            raise _HospitalNotFound()
        hospital_id = hospital.hospital_id

        # FR-B-9 today count
        today_count = (
            session.scalar(
                select(func.count())
                .select_from(Study)
                .where(
                    Study.hospital_pk == hospital_pk,
                    Study.ingested_at >= today_start,
                )
            )
            or 0
        )

        # FR-B-10 cumulative
        cumulative = (
            session.scalar(
                select(func.count()).select_from(Study).where(Study.hospital_pk == hospital_pk)
            )
            or 0
        )

        # FR-B-11 monthly 12m series — ORM aggregate on study.ingested_at.
        # SQLite lacks ``DATE_TRUNC`` so we group in Python. 12 months x single
        # hospital is bounded; no partition scan risk.
        since = (today_start - timedelta(days=400)).replace(day=1)
        rows = session.execute(
            select(Study.ingested_at).where(
                Study.hospital_pk == hospital_pk,
                Study.ingested_at >= since,
            )
        ).all()
        buckets: dict[str, int] = {m: 0 for m in _iter_months(now, 12)}
        for (ts,) in rows:
            if ts is None:
                continue
            key = _month_bucket(ts if ts.tzinfo else ts.replace(tzinfo=UTC))
            if key in buckets:
                buckets[key] += 1
        monthly = [MonthlyStudyCount(year_month=k, count=v) for k, v in buckets.items()]

        # Modality distribution (all-time for this hospital, limit to top 10)
        mod_rows = session.execute(
            select(Study.modality, func.count())
            .where(Study.hospital_pk == hospital_pk)
            .group_by(Study.modality)
            .order_by(func.count().desc())
            .limit(10)
        ).all()
        modality_dist = [
            ModalityCount(modality=m or "UNKNOWN", count=c) for (m, c) in mod_rows if c
        ]

        # Gateway health — piggy-back on latest study.ingested_at as the
        # pragmatic "heartbeat" signal. v0.1.1 will lean on
        # audit_ingest_event for a richer status story; study is a lower-
        # cardinality table so the query stays cheap here too.
        latest_ts = session.scalar(
            select(func.max(Study.ingested_at)).where(Study.hospital_pk == hospital_pk)
        )
        if latest_ts is not None and latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=UTC)
        delta = int((now - latest_ts).total_seconds()) if latest_ts else None
        health = GatewayHealth(
            status=_health_status(delta),
            last_sync_at=latest_ts,
            last_sync_delta_seconds=delta,
        )

    if period == "today":
        monthly = [m for m in monthly if m.year_month == _month_bucket(now)]
    elif period == "30d":
        # Keep just current + previous month for the 30d view.
        last_two = _iter_months(now, 2)
        monthly = [m for m in monthly if m.year_month in last_two]

    stats = StatsResponse(
        hospital_id=hospital_id,
        studies=StudyStats(today=today_count, cumulative=cumulative, monthly_12m=monthly),
        gateway_health=health,
        modality_distribution=modality_dist,
        as_of=now,
    )
    return StatsEnvelope(data=stats)


@router.get(
    "/v1/hospital/me/gateway-health",
    response_model=GatewayHealthEnvelope,
    summary="Hospital Dashboard — Gateway last-heartbeat status label",
)
def get_gateway_health(request: Request) -> GatewayHealthEnvelope:
    hospital_pk, _ = require_hospital(request)
    session_factory = request.app.state.session_factory

    now = datetime.now(tz=UTC)
    with session_factory() as session:
        hospital = session.get(Hospital, hospital_pk)
        if hospital is None:
            raise _HospitalNotFound()
        hospital_id = hospital.hospital_id

        # Pull the most recent study row (cheap) to derive the heartbeat.
        row = session.execute(
            select(Study.ingested_at, Study.gateway_id)
            .where(Study.hospital_pk == hospital_pk)
            .order_by(Study.ingested_at.desc())
            .limit(1)
        ).first()
        if row is None:
            resp = GatewayHealthResponse(
                hospital_id=hospital_id,
                gateway_id=None,
                status="unknown",
                last_sync_at=None,
                last_sync_delta_seconds=None,
                as_of=now,
            )
            return GatewayHealthEnvelope(data=resp)

        latest_ts, gateway_id = row
        if latest_ts is not None and latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=UTC)
        delta = int((now - latest_ts).total_seconds()) if latest_ts else None
        resp = GatewayHealthResponse(
            hospital_id=hospital_id,
            gateway_id=gateway_id,
            status=_health_status(delta),
            last_sync_at=latest_ts,
            last_sync_delta_seconds=delta,
            as_of=now,
        )
    return GatewayHealthEnvelope(data=resp)


# Whitelisted event types shown to the hospital operator — anything outside
# this set is filtered out to avoid leaking internal-only event labels.
_AUDIT_EVENT_WHITELIST: frozenset[str] = frozenset(
    {
        "ingest.accepted",
        "ingest.rejected",
        "upload.completed",
        "anchor.recorded",
        "order.delivered",
    }
)


@router.get(
    "/v1/hospital/me/audit",
    response_model=AuditEnvelope,
    summary="Hospital Dashboard — recent audit events (PHI filtered)",
)
def get_hospital_audit(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
) -> AuditEnvelope:
    hospital_pk, _ = require_hospital(request)
    session_factory = request.app.state.session_factory

    now = datetime.now(tz=UTC)
    with session_factory() as session:
        hospital = session.get(Hospital, hospital_pk)
        if hospital is None:
            raise _HospitalNotFound()
        hospital_id = hospital.hospital_id

        # ORM read: no raw_dicom_tags projection — only timestamp, event name,
        # request_id (re-used as hash_short). ``central_job_id`` is a ULID
        # namespace, safe to expose as a short hash-like string.
        rows = session.execute(
            select(
                AuditIngestEvent.received_at,
                AuditIngestEvent.event,
                AuditIngestEvent.central_job_id,
                AuditIngestEvent.request_id,
                AuditIngestEvent.error_code,
            )
            .where(AuditIngestEvent.hospital_pk == hospital_pk)
            .order_by(AuditIngestEvent.received_at.desc())
            .limit(limit * 4)  # over-fetch to compensate for whitelist filter
        ).all()

    events: list[AuditEvent] = []
    for ts, event_name, central_job_id, request_id, error_code in rows:
        if event_name not in _AUDIT_EVENT_WHITELIST:
            continue
        # Prefer central_job_id (ULID), fall back to request_id — both PHI-safe.
        token_source = central_job_id or request_id or ""
        # Strip a common ``ingest_`` prefix then take first 8 hex-ish chars.
        if token_source.startswith("ingest_"):
            token_source = token_source[len("ingest_") :]
        hash_short = "".join(ch for ch in token_source if ch.isalnum()).lower()[:8]
        if not hash_short:
            hash_short = "00000000"
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        events.append(
            AuditEvent(
                ts=ts,
                event_type=event_name,
                hash_short=hash_short,
                detail_code=error_code,
            )
        )
        if len(events) >= limit:
            break

    return AuditEnvelope(data=AuditResponse(hospital_id=hospital_id, events=events, as_of=now))


__all__ = ["router"]
