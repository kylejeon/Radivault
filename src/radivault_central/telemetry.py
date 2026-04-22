"""Prometheus + OpenTelemetry wiring (dev-spec FR-21, FR-61).

This module is kept dependency-light: we lazily import OTel so tests that don't
need tracing don't pay startup cost.
"""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

log = logging.getLogger("radivault_central.telemetry")

# A dedicated registry lets us reset between tests while keeping label
# cardinality deterministic.
REGISTRY = CollectorRegistry(auto_describe=True)


# -- core metrics (design-spec §4.3, 18 metrics) ------------------------------

INGEST_REQUESTS = Counter(
    "radivault_central_ingest_requests_total",
    "Ingest requests by outcome",
    ["hospital_id", "status"],
    registry=REGISTRY,
)

INGEST_BYTES = Counter(
    "radivault_central_ingest_bytes_total",
    "Cumulative bytes received across successful ingests",
    ["hospital_id"],
    registry=REGISTRY,
)

INGEST_DURATION = Histogram(
    "radivault_central_ingest_duration_seconds",
    "Total ingest request duration",
    ["hospital_id", "outcome"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 300, 600, 900),
    registry=REGISTRY,
)

INGEST_INSTANCES = Counter(
    "radivault_central_ingest_instances_total",
    "DICOM instances accepted",
    ["hospital_id"],
    registry=REGISTRY,
)

IDEMPOTENCY_DEDUP = Counter(
    "radivault_central_idempotency_dedup_total",
    "Idempotency cache decisions",
    ["hospital_id", "result"],
    registry=REGISTRY,
)

AUTH_FAILURES = Counter(
    "radivault_central_auth_failures_total",
    "Authentication failures grouped by reason",
    ["reason"],
    registry=REGISTRY,
)

ANCHOR_REQUESTS = Counter(
    "radivault_central_anchor_requests_total",
    "Anchor requests by outcome",
    ["hospital_id", "status"],
    registry=REGISTRY,
)

ANCHOR_LAG = Gauge(
    "radivault_central_anchor_lag_seconds",
    "Seconds since the most recent anchor for each hospital",
    ["hospital_id"],
    registry=REGISTRY,
)

ANCHOR_CHAIN_BREAKS = Counter(
    "radivault_central_anchor_chain_breaks_total",
    "Count of anchor chain discontinuities detected",
    ["hospital_id"],
    registry=REGISTRY,
)

RATE_LIMIT_HITS = Counter(
    "radivault_central_rate_limit_hits_total",
    "Rate-limit rejections",
    ["hospital_id", "scope"],
    registry=REGISTRY,
)

STORAGE_OPERATIONS = Counter(
    "radivault_central_storage_operations_total",
    "Object store operations",
    ["operation", "outcome"],
    registry=REGISTRY,
)

STORAGE_DURATION = Histogram(
    "radivault_central_storage_duration_seconds",
    "Object store call duration",
    ["operation"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
    registry=REGISTRY,
)

DB_POOL_IN_USE = Gauge(
    "radivault_central_db_pool_in_use",
    "Currently checked-out DB connections",
    registry=REGISTRY,
)

DB_POOL_SIZE = Gauge(
    "radivault_central_db_pool_size",
    "DB connection pool size",
    registry=REGISTRY,
)

REDIS_OPERATIONS = Counter(
    "radivault_central_redis_operations_total",
    "Redis calls",
    ["operation", "outcome"],
    registry=REGISTRY,
)

MANIFEST_REJECTIONS = Counter(
    "radivault_central_manifest_rejections_total",
    "Manifest preflight rejections",
    ["hospital_id", "error_code"],
    registry=REGISTRY,
)

BUILD_INFO = Gauge(
    "radivault_central_build_info",
    "Build metadata (value fixed to 1)",
    ["version", "git_sha", "python_version"],
    registry=REGISTRY,
)

READYZ_CHECKS = Gauge(
    "radivault_central_readyz_checks",
    "Current readyz subcheck status (1=ok, 0=fail)",
    ["check"],
    registry=REGISTRY,
)


def init_telemetry(
    *,
    version: str,
    git_sha: str = "unknown",
    python_version: str = "unknown",
    otlp_endpoint: str | None = None,
    service_name: str = "radivault-central",
) -> None:
    """Set up Prometheus build info label and best-effort OTel exporter.

    If ``otlp_endpoint`` is provided we configure the OTLP HTTP exporter.
    Otherwise a simple console span processor is used (useful in dev). Any OTel
    import failure is logged and swallowed — tracing is not critical-path.
    """
    try:
        BUILD_INFO.labels(version=version, git_sha=git_sha, python_version=python_version).set(1)
    except Exception:  # pragma: no cover
        log.exception("failed to set build_info")

    try:
        _configure_otel(otlp_endpoint=otlp_endpoint, service_name=service_name)
    except Exception as exc:  # pragma: no cover — optional dependency path
        log.warning("otel init skipped: %s", exc)


def _configure_otel(*, otlp_endpoint: str | None, service_name: str) -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter: Any
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        exporter = ConsoleSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
