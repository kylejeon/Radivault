"""Settings for radivault_search (dev-spec §6.5).

Mirrors the shape of ``radivault_central.config`` so operators get one mental
model. YAML (``RV_SEARCH_CONFIG``) overlaid with environment variables.
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
    port: int = 8001


@dataclass
class DbConfig:
    dsn: str = (
        "postgresql+psycopg://radivault_buyer_ro:radivault_buyer_ro"
        "@localhost:5432/radivault_central"
    )
    admin_dsn: str = (
        "postgresql+psycopg://search_admin:search_admin@localhost:5432/radivault_central"
    )
    migration_dsn: str = (
        "postgresql+psycopg://central_migrator:central_migrator@localhost:5432/radivault_central"
    )
    pool_size: int = 30
    max_overflow: int = 20


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/1"
    auth_cache_ttl_seconds: int = 60
    cost_estimate_ttl_seconds: int = 300
    facets_cache_ttl_seconds: int = 900
    hospitals_cache_ttl_seconds: int = 300


@dataclass
class AuthConfig:
    hash_algorithm: str = "argon2id"
    argon_time_cost: int = 3
    argon_memory_cost_kib: int = 65536
    argon_parallelism: int = 2
    global_filter_salt: str = "radivault_search_default_salt"
    api_key_prefix_live: str = "rv_live_"
    api_key_prefix_test: str = "rv_test_"


@dataclass
class TierConfig:
    rpm: int = 20
    daily: int = 100
    concurrency: int = 3
    max_limit_per_page: int = 100


@dataclass
class RateLimitConfig:
    tier_preview: TierConfig = field(
        default_factory=lambda: TierConfig(rpm=20, daily=100, concurrency=3, max_limit_per_page=100)
    )
    tier_paid: TierConfig = field(
        default_factory=lambda: TierConfig(
            rpm=600, daily=10000, concurrency=20, max_limit_per_page=200
        )
    )
    ip_global_per_min: int = 300


@dataclass
class CostConfig:
    max_estimated_rows: int = 10_000_000
    facet_auto_suppress_rows: int = 2_000_000
    cost_estimate_timeout_ms: int = 500


@dataclass
class TimeoutsConfig:
    fastapi_request_timeout_seconds: int = 15
    pg_statement_timeout: str = "10s"
    graceful_drain_seconds: int = 15


@dataclass
class ObservabilityConfig:
    log_level: str = "INFO"
    json_logs: bool = True
    otlp_endpoint: str | None = None
    metrics_path: str = "/metrics"
    sentry_dsn: str | None = None
    log_sanitizer_strict: bool = True


@dataclass
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    db: DbConfig = field(default_factory=DbConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    timeouts: TimeoutsConfig = field(default_factory=TimeoutsConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    @classmethod
    def load(cls, config_path: str | os.PathLike[str] | None = None) -> Settings:
        data: dict[str, Any] = {}
        path = config_path or os.environ.get("RV_SEARCH_CONFIG")
        if path:
            p = Path(path)
            if p.exists():
                loaded = yaml.safe_load(p.read_text()) or {}
                data = _expand_env(loaded)

        app = AppConfig(**(data.get("app") or {}))
        db = DbConfig(**(data.get("db") or {}))
        redis_cfg = RedisConfig(**(data.get("redis") or {}))

        auth_raw = data.get("auth") or {}
        argon = auth_raw.pop("argon2", None) or {}
        auth = AuthConfig(
            hash_algorithm=auth_raw.get("hash_algorithm", "argon2id"),
            argon_time_cost=int(argon.get("time_cost", 3)),
            argon_memory_cost_kib=int(argon.get("memory_cost_kib", 65536)),
            argon_parallelism=int(argon.get("parallelism", 2)),
            global_filter_salt=auth_raw.get("global_filter_salt", "radivault_search_default_salt")
            or "radivault_search_default_salt",
            api_key_prefix_live=auth_raw.get("api_key_prefix_live", "rv_live_"),
            api_key_prefix_test=auth_raw.get("api_key_prefix_test", "rv_test_"),
        )

        rate_raw = data.get("rate_limit") or {}
        preview_raw = rate_raw.get("tier_preview") or {}
        paid_raw = rate_raw.get("tier_paid") or {}
        rate_limit = RateLimitConfig(
            tier_preview=TierConfig(**preview_raw) if preview_raw else TierConfig(),
            tier_paid=TierConfig(**paid_raw)
            if paid_raw
            else TierConfig(rpm=600, daily=10000, concurrency=20, max_limit_per_page=200),
            ip_global_per_min=int(rate_raw.get("ip_global_per_min", 300)),
        )
        cost = CostConfig(**(data.get("cost") or {}))
        timeouts = TimeoutsConfig(**(data.get("timeouts") or {}))
        observability = ObservabilityConfig(**(data.get("observability") or {}))

        s = cls(
            app=app,
            db=db,
            redis=redis_cfg,
            auth=auth,
            rate_limit=rate_limit,
            cost=cost,
            timeouts=timeouts,
            observability=observability,
        )
        s._apply_env_overrides()
        return s

    def _apply_env_overrides(self) -> None:
        env = os.environ
        if v := env.get("DATABASE_URL"):
            self.db.dsn = v
        if v := env.get("ADMIN_DATABASE_URL"):
            self.db.admin_dsn = v
        if v := env.get("MIGRATION_DATABASE_URL"):
            self.db.migration_dsn = v
        if v := env.get("REDIS_URL"):
            self.redis.url = v
        if v := env.get("FILTER_HASH_GLOBAL_SALT"):
            self.auth.global_filter_salt = v
        if v := env.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            self.observability.otlp_endpoint = v
        if v := env.get("SENTRY_DSN"):
            self.observability.sentry_dsn = v
        if v := env.get("RV_SEARCH_LOG_LEVEL"):
            self.observability.log_level = v.upper()
        if v := env.get("RADIVAULT_SEARCH_ENV"):
            self.app.env = v


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, str) and value.startswith("${env:") and value.endswith("}"):
        return os.environ.get(value[6:-1])
    return value
