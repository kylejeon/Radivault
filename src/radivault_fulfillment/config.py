"""Settings for radivault_fulfillment (dev-spec §6.6).

YAML via ``RV_FULFILLMENT_CONFIG`` overlaid with environment variables.
Structure mirrors central/search dataclass style for operator ergonomics.
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
    workers: int = 5
    port: int = 8002


@dataclass
class DbConfig:
    dsn: str = (
        "postgresql+psycopg://radivault_fulfillment_app:radivault_fulfillment_app"
        "@localhost:5432/radivault_central"
    )
    admin_dsn: str = (
        "postgresql+psycopg://central_migrator:central_migrator"
        "@localhost:5432/radivault_central"
    )
    pool_size: int = 30
    max_overflow: int = 20


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/2"
    auth_cache_ttl_seconds: int = 60
    idempotency_ttl_seconds: int = 86400
    long_poll_channel_prefix: str = "transfer_job_hospital:"


@dataclass
class PresignConfig:
    default_ttl_seconds: int = 86400
    min_ttl_seconds: int = 3600
    max_ttl_seconds: int = 604800


@dataclass
class StorageConfig:
    provider: str = "s3"
    endpoint_url: str | None = None
    region: str = "ap-northeast-2"
    bucket: str = "radivault-ingest-dev"
    staging_prefix: str = "staging/"
    ingest_prefix: str = "ingest/"
    kms_key_arn: str | None = None
    force_path_style: bool = True
    access_key_id: str | None = None
    secret_access_key: str | None = None
    presign: PresignConfig = field(default_factory=PresignConfig)


@dataclass
class TierDefaults:
    max_cohort_size: int = 50
    max_order_bytes: int = 10_737_418_240  # 10 GB
    daily_order_quota: int = 5
    download_ttl_max_seconds: int = 86400
    unit_price_usd: float = 5.0


@dataclass
class OrderConfig:
    ttl_seconds: int = 604_800  # 7 days
    estimated_ready_seconds_per_study_hot: float = 0.5
    estimated_ready_seconds_per_study_cold: float = 36.0
    tier_preview: TierDefaults = field(
        default_factory=lambda: TierDefaults(
            max_cohort_size=50,
            max_order_bytes=10_737_418_240,
            daily_order_quota=5,
            download_ttl_max_seconds=86400,
            unit_price_usd=5.0,
        )
    )
    tier_paid: TierDefaults = field(
        default_factory=lambda: TierDefaults(
            max_cohort_size=10_000,
            max_order_bytes=2_199_023_255_552,
            daily_order_quota=50,
            download_ttl_max_seconds=604_800,
            unit_price_usd=5.0,
        )
    )


@dataclass
class TransferJobConfig:
    lease_ttl_seconds: int = 900
    max_retries: int = 5
    retry_backoff_initial_seconds: int = 60
    retry_backoff_factor: int = 2
    retry_backoff_cap_seconds: int = 3600
    long_poll_wait_max_seconds: int = 60
    hospital_concurrency_cap: int = 2


@dataclass
class DownloadConfig:
    rate_limit_mint_per_5s: int = 1
    rate_limit_mint_burst: int = 10
    access_log_etl_enabled: bool = False


@dataclass
class AuditConfig:
    agreement_hash_current: str = "0" * 64  # placeholder; operator sets real SHA-256


@dataclass
class ObservabilityConfig:
    log_level: str = "INFO"
    json_logs: bool = True
    otlp_endpoint: str | None = None
    metrics_path: str = "/metrics"
    sentry_dsn: str | None = None


@dataclass
class LeaseReaperConfig:
    interval_seconds: int = 60
    batch_size: int = 200


@dataclass
class OutboxPollerConfig:
    interval_seconds: int = 2
    batch_size: int = 100


@dataclass
class ExpiryTickerConfig:
    interval_seconds: int = 60
    batch_size: int = 100


@dataclass
class AuthConfig:
    hash_algorithm: str = "argon2id"
    argon_time_cost: int = 3
    argon_memory_cost_kib: int = 65536
    argon_parallelism: int = 2
    api_key_prefix_live: str = "rv_live_"
    api_key_prefix_test: str = "rv_test_"


@dataclass
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    db: DbConfig = field(default_factory=DbConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    order: OrderConfig = field(default_factory=OrderConfig)
    transfer_job: TransferJobConfig = field(default_factory=TransferJobConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    lease_reaper: LeaseReaperConfig = field(default_factory=LeaseReaperConfig)
    outbox_poller: OutboxPollerConfig = field(default_factory=OutboxPollerConfig)
    expiry_ticker: ExpiryTickerConfig = field(default_factory=ExpiryTickerConfig)

    @classmethod
    def load(cls, config_path: str | os.PathLike[str] | None = None) -> Settings:
        data: dict[str, Any] = {}
        path = config_path or os.environ.get("RV_FULFILLMENT_CONFIG")
        if path:
            p = Path(path)
            if p.exists():
                loaded = yaml.safe_load(p.read_text()) or {}
                data = _expand_env(loaded)

        app = AppConfig(**(data.get("app") or {}))
        db = DbConfig(**(data.get("db") or {}))
        redis_cfg = RedisConfig(**(data.get("redis") or {}))

        storage_raw = data.get("storage") or {}
        presign_raw = storage_raw.pop("presign", None) or {}
        storage = StorageConfig(
            **{k: v for k, v in storage_raw.items() if v is not None},
            presign=PresignConfig(**presign_raw) if presign_raw else PresignConfig(),
        )

        auth_raw = data.get("auth") or {}
        argon = auth_raw.pop("argon2", None) or {}
        auth = AuthConfig(
            hash_algorithm=auth_raw.get("hash_algorithm", "argon2id"),
            argon_time_cost=int(argon.get("time_cost", 3)),
            argon_memory_cost_kib=int(argon.get("memory_cost_kib", 65536)),
            argon_parallelism=int(argon.get("parallelism", 2)),
            api_key_prefix_live=auth_raw.get("api_key_prefix_live", "rv_live_"),
            api_key_prefix_test=auth_raw.get("api_key_prefix_test", "rv_test_"),
        )

        order_raw = data.get("order") or {}
        tier_defaults_raw = order_raw.pop("tier_defaults", None) or {}
        order = OrderConfig(
            ttl_seconds=int(order_raw.get("ttl_seconds", 604_800)),
            estimated_ready_seconds_per_study_hot=float(
                order_raw.get("estimated_ready_seconds_per_study_hot", 0.5)
            ),
            estimated_ready_seconds_per_study_cold=float(
                order_raw.get("estimated_ready_seconds_per_study_cold", 36.0)
            ),
            tier_preview=TierDefaults(**(tier_defaults_raw.get("preview") or {}))
            if tier_defaults_raw.get("preview")
            else OrderConfig().tier_preview,
            tier_paid=TierDefaults(**(tier_defaults_raw.get("paid") or {}))
            if tier_defaults_raw.get("paid")
            else OrderConfig().tier_paid,
        )
        transfer_job = TransferJobConfig(**(data.get("transfer_job") or {}))
        download = DownloadConfig(**(data.get("download") or {}))
        audit = AuditConfig(**(data.get("audit") or {}))
        observability = ObservabilityConfig(**(data.get("observability") or {}))
        lease_reaper = LeaseReaperConfig(**(data.get("lease_reaper") or {}))
        outbox_poller = OutboxPollerConfig(**(data.get("outbox_poller") or {}))
        expiry_ticker = ExpiryTickerConfig(**(data.get("expiry_ticker") or {}))

        s = cls(
            app=app,
            db=db,
            redis=redis_cfg,
            storage=storage,
            auth=auth,
            order=order,
            transfer_job=transfer_job,
            download=download,
            audit=audit,
            observability=observability,
            lease_reaper=lease_reaper,
            outbox_poller=outbox_poller,
            expiry_ticker=expiry_ticker,
        )
        s._apply_env_overrides()
        return s

    def _apply_env_overrides(self) -> None:
        env = os.environ
        if v := env.get("FULFILLMENT_APP_DSN"):
            self.db.dsn = v
        if v := env.get("FULFILLMENT_ADMIN_DSN"):
            self.db.admin_dsn = v
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
        if v := env.get("AGREEMENT_HASH_CURRENT"):
            self.audit.agreement_hash_current = v
        if v := env.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            self.observability.otlp_endpoint = v
        if v := env.get("SENTRY_DSN"):
            self.observability.sentry_dsn = v
        if v := env.get("RV_FULFILLMENT_LOG_LEVEL"):
            self.observability.log_level = v.upper()
        if v := env.get("RADIVAULT_FULFILLMENT_ENV"):
            self.app.env = v


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, str) and value.startswith("${env:") and value.endswith("}"):
        return os.environ.get(value[6:-1])
    return value
