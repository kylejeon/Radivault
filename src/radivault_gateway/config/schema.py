"""Pydantic v2 models for the gateway configuration (dev-spec §6.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gateway_id: str = Field(min_length=1)
    hospital_id: str = Field(min_length=1)
    org_root_oid: str = Field(min_length=1)

    @field_validator("org_root_oid")
    @classmethod
    def _oid_shape(cls, value: str) -> str:
        # DICOM UID allowed chars: digits and dots; length <= 64.
        if not value.replace(".", "").isdigit():
            raise ValueError("org_root_oid must contain only digits and dots")
        if len(value) > 48:
            raise ValueError("org_root_oid too long (must leave room for suffix within 64 chars)")
        return value


class PacsAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bearer", "basic"] = "bearer"
    token: str | None = None
    username: str | None = None
    password: str | None = None

    @field_validator("token")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class PacsQueryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modalities: list[str] = Field(default_factory=lambda: ["CR", "CT", "MR", "DX"])
    lookback_days: int = Field(default=7, ge=1, le=365)


class PacsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    auth: PacsAuthConfig
    ca_bundle: Path | None = None
    max_concurrency: int = Field(default=4, ge=1, le=32)
    poll_interval_seconds: int = Field(default=300, ge=30, le=86400)
    query: PacsQueryConfig = Field(default_factory=PacsQueryConfig)


class RetainOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitudinal_dates: bool = True
    patient_characteristics: bool = True
    clean_descriptors: bool = True
    clean_graphics: bool = True
    safe_private: bool = False
    uids: bool = False
    institution_identity: bool = False
    device_identity: Literal["full", "partial", "none"] = "partial"


class DeidConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ruleset_version: str = "v0.1.0"
    salt: str = Field(min_length=8)
    salt_version: int = Field(default=1, ge=1)
    burnin_quarantine_modalities: list[str] = Field(default_factory=lambda: ["SC", "US", "OT"])
    retain_options: RetainOptions = Field(default_factory=RetainOptions)


class StagingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: Path
    retention_hours: int = Field(default=72, ge=1)
    max_disk_pct: int = Field(default=80, ge=10, le=99)


class StateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: Path


class AuditConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path
    anchor_interval_seconds: int = Field(default=3600, ge=60)


class CentralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    upload_token: str = Field(min_length=1)
    upload_timeout_seconds: int = Field(default=600, ge=10)
    max_upload_retries: int = Field(default=10, ge=1, le=50)
    # H-1: TLS 1.3 outbound-only (dev-spec §5, §12.3). Default rejects
    # ``http://`` base URLs. Flip to True for local dev against the mock
    # central; the UploadClient will log a WARN at startup.
    allow_insecure: bool = False


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"] = "INFO"
    json_output: bool = Field(default=True, alias="json")
    console_color: Literal["auto", "always", "never"] = "auto"


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    agent: AgentConfig
    pacs: PacsConfig
    deid: DeidConfig
    staging: StagingConfig
    state: StateConfig
    audit: AuditConfig
    central: CentralConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @field_validator("version")
    @classmethod
    def _version_1(cls, value: int) -> int:
        if value != 1:
            raise ValueError(f"unsupported config version {value} (expected 1)")
        return value
