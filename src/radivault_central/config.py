"""Pydantic settings for Central Ingest (dev-spec §6.6 / FR-64..69).

Loaded from environment variables with ``RV_CENTRAL_`` prefix or from a
YAML file pointed to by ``RV_CENTRAL_CONFIG``. Defaults match the
``configs/central.example.yaml`` shape.

Note: we intentionally do *not* use the ``RADIVAULT_`` prefix — that namespace
is owned by the Gateway Agent config loader which treats every
``RADIVAULT_<key>`` env var as a top-level config override and will reject
unknowns as ``extra`` inputs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    env: str = "dev"
    api_contract_version: str = "1"
    workers: int = 2


@dataclass
class DbConfig:
    dsn: str = "postgresql+psycopg://central_app:central_app@localhost:5432/central"
    migration_dsn: str = (
        "postgresql+psycopg://central_migrator:central_migrator@localhost:5432/central"
    )
    pool_size: int = 10
    max_overflow: int = 10


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/0"
    idempotency_ttl_seconds: int = 86400


@dataclass
class StorageConfig:
    provider: str = "local"  # 's3' | 'minio' | 'local'
    endpoint_url: str | None = None
    region: str = "ap-northeast-2"
    bucket: str = "radivault-ingest-dev"
    kms_key_arn: str | None = None
    force_path_style: bool = True
    access_key_id: str | None = None
    secret_access_key: str | None = None
    local_root: str = "/var/lib/radivault-central/objects"


@dataclass
class AuthConfig:
    hash_algorithm: str = "argon2id"
    argon_time_cost: int = 3
    argon_memory_cost_kib: int = 65536
    argon_parallelism: int = 2


@dataclass
class RateLimitConfig:
    hospital_ingest_per_min: int = 60
    hospital_ingest_per_hour: int = 2000
    hospital_anchor_per_min: int = 6
    ip_global_per_min: int = 300
    max_concurrent_uploads_default: int = 4


@dataclass
class ObservabilityConfig:
    log_level: str = "INFO"
    json_logs: bool = True
    otlp_endpoint: str | None = None
    metrics_path: str = "/metrics"
    sentry_dsn: str | None = None


@dataclass
class OpsConfig:
    anchor_lag_warn_seconds: int = 10800
    anchor_lag_block_enabled: bool = False
    max_manifest_bytes: int = 1048576


@dataclass
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    db: DbConfig = field(default_factory=DbConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    ops: OpsConfig = field(default_factory=OpsConfig)

    @classmethod
    def load(cls, config_path: str | os.PathLike[str] | None = None) -> Settings:
        """Load settings from YAML (if any) overlaid with environment variables.

        Environment variables take precedence. See config.example.yaml for keys.
        Simple envvar expansion ``${env:VAR}`` is supported inside YAML values.
        """
        data: dict[str, Any] = {}
        path = config_path or os.environ.get("RV_CENTRAL_CONFIG")
        if path:
            p = Path(path)
            if p.exists():
                loaded = yaml.safe_load(p.read_text()) or {}
                data = _expand_env(loaded)

        app = AppConfig(**(data.get("app") or {}))
        db = DbConfig(**(data.get("db") or {}))
        redis_cfg = RedisConfig(**(data.get("redis") or {}))

        storage_raw = data.get("storage") or {}
        storage = StorageConfig(**{k: v for k, v in storage_raw.items() if v is not None})

        auth_raw = data.get("auth") or {}
        argon = auth_raw.pop("argon2", None) or {}
        auth = AuthConfig(
            hash_algorithm=auth_raw.get("hash_algorithm", "argon2id"),
            argon_time_cost=int(argon.get("time_cost", 3)),
            argon_memory_cost_kib=int(argon.get("memory_cost_kib", 65536)),
            argon_parallelism=int(argon.get("parallelism", 2)),
        )
        rate_limit = RateLimitConfig(**(data.get("rate_limit") or {}))
        observability = ObservabilityConfig(**(data.get("observability") or {}))
        ops = OpsConfig(**(data.get("ops") or {}))

        s = cls(
            app=app,
            db=db,
            redis=redis_cfg,
            storage=storage,
            auth=auth,
            rate_limit=rate_limit,
            observability=observability,
            ops=ops,
        )
        s._apply_env_overrides()
        return s

    def _apply_env_overrides(self) -> None:
        """Apply explicit envvar overrides that operators use most often."""
        env = os.environ
        if v := env.get("DATABASE_URL"):
            self.db.dsn = v
        if v := env.get("MIGRATION_DATABASE_URL"):
            self.db.migration_dsn = v
        if v := env.get("REDIS_URL"):
            self.redis.url = v
        if v := env.get("S3_ENDPOINT_URL"):
            self.storage.endpoint_url = v
        if v := env.get("S3_BUCKET"):
            self.storage.bucket = v
        if v := env.get("S3_REGION"):
            self.storage.region = v
        if v := env.get("S3_KMS_KEY_ARN"):
            self.storage.kms_key_arn = v
        if v := env.get("S3_ACCESS_KEY_ID"):
            self.storage.access_key_id = v
        if v := env.get("S3_SECRET_ACCESS_KEY"):
            self.storage.secret_access_key = v
        if v := env.get("S3_PROVIDER"):
            self.storage.provider = v
        if v := env.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            self.observability.otlp_endpoint = v
        if v := env.get("SENTRY_DSN"):
            self.observability.sentry_dsn = v
        if v := env.get("RV_CENTRAL_LOG_LEVEL"):
            self.observability.log_level = v.upper()
        if v := env.get("IDEMPOTENCY_TTL_SECONDS"):
            self.redis.idempotency_ttl_seconds = int(v)
        if v := env.get("RADIVAULT_ENV"):
            self.app.env = v


def _expand_env(value: Any) -> Any:
    """Expand ``${env:VAR}`` placeholders recursively in YAML-loaded structures."""
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, str) and value.startswith("${env:") and value.endswith("}"):
        return os.environ.get(value[6:-1])
    return value
