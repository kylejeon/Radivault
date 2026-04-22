"""Withdraw stub endpoint (dev-spec FR-73)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from radivault_central.audit.ingest_event import record_ingest_event
from radivault_central.auth.middleware import require_hospital
from radivault_central.errors import NotImplementedStub

router = APIRouter()


@router.post("/v1/studies/{pseudo_study_uid}/withdraw-stub", status_code=501)
def withdraw_stub(pseudo_study_uid: str, request: Request) -> None:
    hospital_pk, _hospital_id = require_hospital(request)
    session_factory = request.app.state.session_factory
    request_id = getattr(request.state, "request_id", "unknown")
    with session_factory() as session:
        record_ingest_event(
            session,
            hospital_pk=hospital_pk,
            gateway_id="withdraw-stub",
            event="withdraw.stub.invoked",
            status_code=501,
            request_id=request_id,
            pseudo_study_uid=pseudo_study_uid,
        )
        session.commit()
    raise NotImplementedStub(detail="Withdraw flow deferred to v0.2")
