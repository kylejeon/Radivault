"""Pydantic v2 models for the gateway configuration (dev-spec §6.2).

Multi-PACS sync extension (FR-MPS-1, FR-MPS-6 — dev-spec
``docs/specs/dev-spec-multi-pacs-sync.md``):

- ``pacs:`` now accepts either the legacy mapping (single PACS) or a list
  of PACS endpoints. ``GatewayConfig`` normalises both shapes via a
  ``model_validator(mode='before')`` and exposes:

  - ``cfg.pacs`` — first / primary endpoint as a legacy :class:`PacsConfig`,
    preserving backward compatibility for every existing read site.
  - ``cfg.pacs_endpoints`` — full list of :class:`PacsEndpointConfig`
    instances (id, hospital_id override, priority, enabled, plus all
    PacsConfig fields). The orchestrator iterates this list.

- ``central.upload_tokens: dict[hospital_id -> token]`` is added beside the
  legacy ``central.upload_token`` (now optional). ``token_for_hospital()``
  resolves with map-first / legacy-fallback semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from radivault_gateway.deid.pixel.config import PixelDeidConfig


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


class PacsEndpointConfig(PacsConfig):
    """One PACS endpoint inside a multi-PACS deployment (FR-MPS-1).

    Inherits all transport/auth/query fields from :class:`PacsConfig` so the
    legacy reads (``cfg.pacs.base_url``, ``cfg.pacs.auth``, …) keep working
    when callers pick a single endpoint. Adds the multi-PACS specific
    bookkeeping fields:

    - ``id`` — unique label inside a config (``[a-z0-9_-]{1,32}``). Defaulted
      to ``"default"`` by the legacy normaliser when the operator omits it.
    - ``hospital_id`` — optional override; ``None`` means "fall back to
      ``agent.hospital_id``" (FR-MPS-4 — single-hospital, multi-PACS case).
    - ``priority`` — sort key. Lower runs first.
    - ``enabled`` — gates whether sync-once iterates this endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default="default",
        pattern=r"^[a-z0-9_-]{1,32}$",
        description="PACS identifier, unique within the gateway config",
    )
    hospital_id: str | None = Field(
        default=None,
        description="Hospital scope override; defaults to agent.hospital_id",
    )
    priority: int = Field(
        default=100,
        ge=0,
        description="Sort order for sequential sync (lower runs first)",
    )
    enabled: bool = True


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
    # v0.2 de-id-pixel extension (opt-in, default OFF).
    pixel: PixelDeidConfig = Field(default_factory=PixelDeidConfig)


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
    # FR-MPS-6 / K-MPS-6: ``upload_tokens`` is the new per-hospital map.
    # ``upload_token`` is preserved as an optional legacy fallback so the
    # single-PACS demo configs keep working unchanged. At least one of the
    # two must be supplied — enforced by ``_require_upload_credential`` below.
    upload_token: str | None = Field(default=None, min_length=1)
    upload_tokens: dict[str, str] | None = None
    upload_timeout_seconds: int = Field(default=600, ge=10)
    max_upload_retries: int = Field(default=10, ge=1, le=50)
    # H-1: TLS 1.3 outbound-only (dev-spec §5, §12.3). Default rejects
    # ``http://`` base URLs. Flip to True for local dev against the mock
    # central; the UploadClient will log a WARN at startup.
    allow_insecure: bool = False

    @model_validator(mode="after")
    def _require_upload_credential(self) -> "CentralConfig":
        if not self.upload_token and not self.upload_tokens:
            raise ValueError(
                "central.upload_token or central.upload_tokens must be set"
            )
        if self.upload_tokens is not None:
            for hosp, tok in self.upload_tokens.items():
                if not isinstance(tok, str) or not tok.strip():
                    raise ValueError(
                        f"central.upload_tokens['{hosp}'] must be a non-empty string"
                    )
        return self

    def token_for_hospital(self, hospital_id: str) -> str:
        """Return the upload bearer for a given hospital_id.

        Resolution order (FR-MPS-6 / K-MPS-6):
          1. ``upload_tokens[hospital_id]`` if the map is configured and the
             key exists.
          2. Legacy ``upload_token`` fallback.
          3. ``KeyError`` when neither is available.
        """
        if self.upload_tokens and hospital_id in self.upload_tokens:
            return self.upload_tokens[hospital_id]
        if self.upload_token:
            return self.upload_token
        raise KeyError(
            f"no central upload token configured for hospital_id='{hospital_id}' "
            "(set central.upload_tokens[hospital_id] or central.upload_token)"
        )


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"] = "INFO"
    json_output: bool = Field(default=True, alias="json")
    console_color: Literal["auto", "always", "never"] = "auto"


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    agent: AgentConfig
    # ``pacs`` exposes the legacy single-PACS shape (first endpoint sorted by
    # priority) so all existing reads (``cfg.pacs.base_url``,
    # ``cfg.pacs.poll_interval_seconds`` for the daemon scheduler, …) keep
    # working unchanged. Multi-PACS callers iterate ``cfg.pacs_endpoints``
    # instead. See module docstring + FR-MPS-1.
    pacs: PacsEndpointConfig
    pacs_endpoints: list[PacsEndpointConfig]
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

    @model_validator(mode="before")
    @classmethod
    def _normalise_pacs_block(cls, data: Any) -> Any:
        """Accept either legacy single ``pacs:`` mapping or list of endpoints.

        Normalisation rules (FR-MPS-1):

        - dict / mapping  → wrap in a single-element list. ``id`` defaults to
          ``"default"`` when omitted.
        - list / sequence → each item is a :class:`PacsEndpointConfig`. ``id``
          must be unique across the list.

        Both shapes populate the synthetic ``pacs`` field (first endpoint by
        priority, then config order) and the ``pacs_endpoints`` list. The
        operator never writes ``pacs_endpoints`` directly; it is intentionally
        derived so a single source of truth (``pacs:``) drives the wire shape.
        """
        if not isinstance(data, dict):
            return data
        raw = data.get("pacs")
        if raw is None:
            # Let the standard "missing required field" error surface from
            # GatewayConfig validation.
            return data
        if isinstance(raw, dict):
            entry = dict(raw)
            entry.setdefault("id", "default")
            entries: list[dict] = [entry]
        elif isinstance(raw, list):
            if not raw:
                raise ValueError("pacs: at least one endpoint required")
            entries = []
            for idx, item in enumerate(raw):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"pacs[{idx}]: each endpoint must be a mapping, got "
                        f"{type(item).__name__}"
                    )
                entry = dict(item)
                if "id" not in entry:
                    raise ValueError(
                        f"pacs[{idx}]: 'id' is required for list-form pacs config"
                    )
                entries.append(entry)
            seen: set[str] = set()
            for entry in entries:
                pid = entry["id"]
                if pid in seen:
                    raise ValueError(
                        f"pacs: endpoint id '{pid}' is duplicated; ids must be unique"
                    )
                seen.add(pid)
        else:
            raise ValueError(
                f"pacs: must be a mapping (single PACS) or list of mappings "
                f"(multi-PACS); got {type(raw).__name__}"
            )

        # Sort by (priority, original index) so callers see a deterministic
        # ordering. Disabled endpoints stay in the list — callers filter via
        # ``enabled_endpoints()`` so ``--list-pacs`` can still surface them.
        ordered = sorted(
            enumerate(entries),
            key=lambda pair: (int(pair[1].get("priority", 100)), pair[0]),
        )
        sorted_entries = [entry for _, entry in ordered]

        new_data = dict(data)
        new_data["pacs_endpoints"] = sorted_entries
        # Synthetic ``pacs`` (legacy shape) — pick the first endpoint after
        # the priority sort. This is the endpoint the daemon-mode scheduler
        # uses for ``poll_interval_seconds`` / ``cfg.pacs.query`` reads.
        new_data["pacs"] = sorted_entries[0]
        return new_data

    def enabled_endpoints(self) -> list[PacsEndpointConfig]:
        """Return enabled endpoints in priority order (FR-MPS-2).

        Disabled endpoints are dropped silently — the orchestrator never
        iterates them. ``sync-once --list-pacs`` calls ``self.pacs_endpoints``
        directly so disabled rows still appear in the operator-facing table.
        """
        return [e for e in self.pacs_endpoints if e.enabled]

    def hospital_id_for(self, endpoint: PacsEndpointConfig) -> str:
        """Resolve effective hospital_id for an endpoint (FR-MPS-4)."""
        return endpoint.hospital_id or self.agent.hospital_id
