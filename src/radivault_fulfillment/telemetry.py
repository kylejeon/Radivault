"""Prometheus + OpenTelemetry for radivault_fulfillment (dev-spec FR-81/83).

All metrics use the ``radivault_fulfillment_*`` prefix per FR-81.
"""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

log = logging.getLogger("radivault_fulfillment.telemetry")

REGISTRY = CollectorRegistry(auto_describe=True)


ORDER_SUBMISSIONS_TOTAL = Counter(
    "radivault_fulfillment_order_submissions_total",
    "Orders accepted by POST /v1/orders",
    ["tier", "status"],
    registry=REGISTRY,
)

ORDER_STATE_DURATION = Histogram(
    "radivault_fulfillment_order_state_duration_seconds",
    "Residence time in a given order state",
    ["state"],
    buckets=(0.1, 0.5, 1, 2, 5, 15, 30, 60, 300, 900, 3600),
    registry=REGISTRY,
)

ORDER_END_TO_END = Histogram(
    "radivault_fulfillment_order_end_to_end_seconds",
    "Order submit -> ready_for_download duration",
    ["tier", "path"],
    buckets=(1, 5, 10, 30, 60, 300, 900, 3600, 7200),
    registry=REGISTRY,
)

TRANSFER_JOB_QUEUE_DEPTH = Gauge(
    "radivault_fulfillment_transfer_job_queue_depth",
    "transfer_job rows with state=queued",
    ["hospital_id"],
    registry=REGISTRY,
)

TRANSFER_JOB_CLAIM_TOTAL = Counter(
    "radivault_fulfillment_transfer_job_claim_total",
    "Long-poll claims served",
    ["hospital_id"],
    registry=REGISTRY,
)

TRANSFER_JOB_COMPLETION_SECONDS = Histogram(
    "radivault_fulfillment_transfer_job_completion_seconds",
    "Time from claim to completion",
    ["hospital_id"],
    buckets=(1, 5, 10, 60, 300, 900, 3600),
    registry=REGISTRY,
)

TRANSFER_JOB_FAILURES_TOTAL = Counter(
    "radivault_fulfillment_transfer_job_failures_total",
    "Failed job reports",
    ["hospital_id", "reason_code"],
    registry=REGISTRY,
)

DLQ_DEPTH = Gauge(
    "radivault_fulfillment_dlq_depth",
    "Dead-letter queue size (unresolved)",
    registry=REGISTRY,
)

URL_MINT_TOTAL = Counter(
    "radivault_fulfillment_url_mint_total",
    "Presigned URL mint events",
    ["tier"],
    registry=REGISTRY,
)

URL_MINT_RATE_LIMITED_TOTAL = Counter(
    "radivault_fulfillment_url_mint_rate_limited_total",
    "URL mint requests throttled",
    registry=REGISTRY,
)

DOWNLOAD_BYTES_TOTAL = Counter(
    "radivault_fulfillment_download_bytes_total",
    "Cumulative bytes delivered (v0.1.1 from S3 access log ETL)",
    ["tier"],
    registry=REGISTRY,
)

CANCELLATION_TOTAL = Counter(
    "radivault_fulfillment_cancellation_total",
    "Cancellations by origin state and actor",
    ["tier", "from_state", "actor"],
    registry=REGISTRY,
)

EXPIRED_ORDERS_TOTAL = Counter(
    "radivault_fulfillment_expired_orders_total",
    "Orders transitioned to expired by the ticker",
    registry=REGISTRY,
)

AUTH_FAILURES_TOTAL = Counter(
    "radivault_fulfillment_auth_failures_total",
    "Authentication failures",
    ["plane", "reason"],
    registry=REGISTRY,
)

OUTBOX_BACKLOG = Gauge(
    "radivault_fulfillment_outbox_backlog",
    "Undispatched order_outbox rows",
    registry=REGISTRY,
)

CACHE_HIT_TOTAL = Counter(
    "radivault_fulfillment_cache_hit_total",
    "Cache hit by layer",
    ["cache_layer"],
    registry=REGISTRY,
)

BUILD_INFO = Counter(
    "radivault_fulfillment_build_info",
    "Build metadata",
    ["version", "git_sha", "python_version"],
    registry=REGISTRY,
)


def init_telemetry(
    *,
    version: str,
    git_sha: str = "unknown",
    python_version: str = "unknown",
    otlp_endpoint: str | None = None,
    service_name: str = "radivault-fulfillment",
) -> None:
    try:
        BUILD_INFO.labels(version=version, git_sha=git_sha, python_version=python_version).inc(0)
    except Exception:  # pragma: no cover
        log.exception("build_info set failed")
    try:
        _configure_otel(otlp_endpoint=otlp_endpoint, service_name=service_name)
    except Exception as exc:  # pragma: no cover
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
