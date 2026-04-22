"""FastAPI mock central implementing the dev-spec §7.3 contract.

Development/testing only. Accepts multipart POST ``/v1/ingest/studies`` and
returns 202 + ``{"job_id": "..."}``. Dumps manifest + file metadata to a
temporary directory for test assertions.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile

from radivault_mock_central.schemas import (
    AnchorRequest,
    AnchorResponse,
    HealthResponse,
    IngestResponse,
)

EXPECTED_TOKEN = os.environ.get("MOCK_CENTRAL_TOKEN", "mock-upload-token")
DUMP_ROOT = Path(os.environ.get("MOCK_CENTRAL_DUMP", "/tmp/mock-central"))
DUMP_ROOT.mkdir(parents=True, exist_ok=True)


app = FastAPI(
    title="RadiVault Mock Central",
    version="0.1.0",
    description="Development mock — NOT for production use.",
)


def _auth(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    if token != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/v1/ingest/studies", response_model=IngestResponse, status_code=202)
async def ingest_studies(
    request: Request,
    manifest: Annotated[UploadFile, File(...)],
    files: Annotated[list[UploadFile] | None, File(...)] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    _auth(authorization)
    manifest_bytes = await manifest.read()
    try:
        manifest_obj = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid_manifest: {exc}") from exc

    if "pseudo_study_uid" not in manifest_obj or "gateway_id" not in manifest_obj:
        raise HTTPException(status_code=400, detail="invalid_manifest")

    # Verify sha256s
    expected_map = {f["filename"]: f["sha256"] for f in manifest_obj.get("files", [])}
    dump_dir = DUMP_ROOT / manifest_obj["pseudo_study_uid"]
    dump_dir.mkdir(parents=True, exist_ok=True)
    (dump_dir / "manifest.json").write_bytes(manifest_bytes)
    received = []
    for file in files or []:
        data = await file.read()
        digest = hashlib.sha256(data).hexdigest()
        expected = expected_map.get(file.filename)
        if expected and expected != digest:
            raise HTTPException(
                status_code=400,
                detail=f"invalid_manifest: sha256 mismatch for {file.filename}",
            )
        (dump_dir / file.filename).write_bytes(data)
        received.append(file.filename)

    job_id = "ingest_" + secrets.token_hex(6)
    received_at = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return IngestResponse(job_id=job_id, received_at=received_at)


@app.post("/v1/audit/anchor", response_model=AnchorResponse, status_code=200)
async def audit_anchor(
    payload: AnchorRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> AnchorResponse:
    _auth(authorization)
    dump_dir = DUMP_ROOT / "_anchors"
    dump_dir.mkdir(parents=True, exist_ok=True)
    record = payload.model_dump()
    (dump_dir / f"{payload.anchored_at.replace(':', '-')}.json").write_text(
        json.dumps(record, indent=2)
    )
    return AnchorResponse(anchor_id="anc_" + secrets.token_hex(6))
