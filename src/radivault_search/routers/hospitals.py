"""``GET /v1/search/hospitals`` (dev-spec §7.4)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from radivault_central.db.models import Hospital, Study
from radivault_search.auth.middleware import require_buyer
from radivault_search.errors import ScopeForbidden
from radivault_search.query.executor import compute_hospital_opaque_id
from radivault_search.query.schema import HospitalItem, HospitalsResponse

log = logging.getLogger("radivault_search.hospitals")

router = APIRouter()


@router.get("/v1/search/hospitals")
async def list_hospitals(
    request: Request,
    include_names: bool = Query(default=False),
) -> JSONResponse:
    buyer_pk, _buyer_id, tier, _kid = require_buyer(request)
    scope_json = getattr(request.state, "scope_json", {}) or {}

    if include_names and (tier != "paid" or not scope_json.get("include_hospital_names")):
        raise ScopeForbidden(
            detail="include_names requires paid tier + include_hospital_names scope"
        )

    settings = request.app.state.settings
    factory = request.app.state.session_factory

    with factory() as session:
        rows = list(
            session.execute(
                select(
                    Study.hospital_pk,
                    func.count(Study.study_pk),
                    func.min(Study.study_date_shifted),
                    func.max(Study.study_date_shifted),
                ).group_by(Study.hospital_pk)
            ).all()
        )
        modalities_by_hospital: dict[int, list[str]] = {}
        mod_rows = session.execute(select(Study.hospital_pk, Study.modality).distinct()).all()
        for hpk, mod in mod_rows:
            if mod is None:
                continue
            modalities_by_hospital.setdefault(hpk, []).append(mod)
        hospital_name_map: dict[int, str] = {}
        if include_names:
            for row in session.scalars(select(Hospital)).all():
                hospital_name_map[row.hospital_pk] = row.name

    items: list[HospitalItem] = []
    for hpk, count, first_date, last_date in rows:
        items.append(
            HospitalItem(
                hospital_opaque_id=compute_hospital_opaque_id(
                    hospital_pk=hpk,
                    global_salt=settings.auth.global_filter_salt,
                    buyer_pk=buyer_pk,
                ),
                study_count=int(count or 0),
                first_study_date=(first_date.date() if hasattr(first_date, "date") else first_date),
                last_study_date=(last_date.date() if hasattr(last_date, "date") else last_date),
                modalities=sorted(set(modalities_by_hospital.get(hpk, []))),
                name_public=hospital_name_map.get(hpk) if include_names else None,
            )
        )
    resp = HospitalsResponse(items=items, total_hospitals=len(items))
    return JSONResponse(status_code=200, content=resp.model_dump(mode="json"))
