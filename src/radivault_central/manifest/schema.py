"""Pydantic v2 manifest schema (dev-spec §6.5).

The schema is a **superset** of the Gateway Agent v0.1 manifest — it requires
``anonymization_flag`` in addition to everything Gateway already sends. See
Gateway dev-spec §6.4 and Central dev-spec §13 (delta D-3) for the cross-team
contract.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeidBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    ruleset_version: str
    salt_version: int
    method_code_sequence: list[str] = Field(min_length=1)


class ManifestFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    filename: str
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    bytes: int = Field(ge=0)


class AuditRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    seq: int
    hash: str


class Manifest(BaseModel):
    """Canonical ingest manifest (dev-spec §6.5)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    manifest_version: int
    gateway_id: str
    hospital_id: str
    pseudo_study_uid: str
    modalities: list[str] = Field(min_length=1)
    n_instances: int = Field(ge=1)
    total_bytes: int = Field(ge=0)
    deid: DeidBlock
    anonymization_flag: str
    files: list[ManifestFile] = Field(min_length=1)
    generated_at: str
    audit_ref: AuditRef | None = None

    @field_validator("anonymization_flag")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip()

    def primary_modality(self) -> str | None:
        if not self.modalities:
            return None
        return self.modalities[0]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ManifestMetadataOnly(Manifest):
    """Metadata-only ingest manifest (Flow A — dev-spec ARCHITECTURE.md §4).

    Relaxes :class:`Manifest` so the Gateway can stream the study's metadata
    without the DICOM pixel payload. The schema still asserts every field the
    full-payload manifest asserts (including ``anonymization_flag`` D-3), but
    ``files`` may be empty and ``n_instances`` may be 0. Downstream callers
    build the study row in ``central.study`` with
    ``central_object_present=False`` so the fulfillment subsystem treats the
    row as cold storage that must be pulled from the gateway at order time.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    n_instances: int = Field(ge=0)
    files: list[ManifestFile] = Field(default_factory=list, min_length=0)
