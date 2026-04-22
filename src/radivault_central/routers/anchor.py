"""``POST /v1/audit/anchor`` router (dev-spec §4.2, §8.2)."""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, ValidationError
from ulid import ULID

from radivault_central.audit.anchor import insert_anchor
from radivault_central.auth.middleware import require_hospital
from radivault_central.errors import AnchorSchema, AuthMismatch
from radivault_central.telemetry import ANCHOR_LAG, ANCHOR_REQUESTS

log = logging.getLogger("radivault_central.routers.anchor")

router = APIRouter()


class AnchorRequest(BaseModel):
    gateway_id: str
    seq_range: list[int] = Field(min_length=2, max_length=2)
    head_hash: str
    anchored_at: str


@router.post("/v1/audit/anchor", status_code=200)
def post_anchor(payload: dict, request: Request) -> dict:
    try:
        parsed = AnchorRequest.model_validate(payload)
    except ValidationError as exc:
        raise AnchorSchema(detail=str(exc)) from exc

    hospital_pk, hospital_id = require_hospital(request)

    # Parse timestamp
    try:
        anchored_at = _parse_iso(parsed.anchored_at)
    except ValueError as exc:
        raise AnchorSchema(detail=f"anchored_at parse error: {exc}") from exc

    # Parse head_hash — accept `sha256:<hex>` or hex-only.
    raw_hash = parsed.head_hash
    if raw_hash.startswith("sha256:"):
        raw_hash = raw_hash.split(":", 1)[1]
    try:
        head_hash_bytes = (
            bytes.fromhex(raw_hash)
            if all(c in "0123456789abcdefABCDEF" for c in raw_hash)
            else base64.b64decode(raw_hash)
        )
    except Exception as exc:  # pragma: no cover
        raise AnchorSchema(detail=f"head_hash decode failed: {exc}") from exc

    session_factory = request.app.state.session_factory
    with session_factory() as session:
        # Cross check hospital <-> gateway_id (v0.1 permissive — gateway map only)
        hospital = request.app.state.get_hospital(session, hospital_pk)
        if hospital is None:
            raise AuthMismatch()
        anchor = insert_anchor(
            session,
            hospital_pk=hospital_pk,
            gateway_id=parsed.gateway_id,
            seq_lo=parsed.seq_range[0],
            seq_hi=parsed.seq_range[1],
            head_hash=head_hash_bytes,
            anchored_at=anchored_at,
        )
        session.commit()
        anchor_id = f"anc_{ULID()!s}"
        ANCHOR_REQUESTS.labels(hospital_id=hospital_id, status="accepted").inc()
        ANCHOR_LAG.labels(hospital_id=hospital_id).set(
            max((datetime.now(tz=UTC) - anchored_at).total_seconds(), 0.0)
        )
    return {
        "anchor_id": anchor_id,
        "accepted_at": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "anchor_pk": anchor.anchor_pk,
    }


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
