"""Pydantic schemas for the mock central server (dev-spec §7.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    job_id: str
    received_at: str


class AnchorRequest(BaseModel):
    gateway_id: str
    seq_range: list[int] = Field(min_length=2, max_length=2)
    head_hash: str
    anchored_at: str


class AnchorResponse(BaseModel):
    anchor_id: str


class HealthResponse(BaseModel):
    status: str
