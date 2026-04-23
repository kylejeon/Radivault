"""Prometheus + OpenTelemetry for radivault_search (dev-spec FR-46/FR-48).

All counters/histograms use the ``radivault_index_*`` prefix per FR-46.
"""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Histogram

log = logging.getLogger("radivault_search.telemetry")

REGISTRY = CollectorRegistry(auto_describe=True)


SEARCH_DURATION = Histogram(
    "radivault_index_search_duration_seconds",
    "Search request duration",
    ["tier", "endpoint", "status", "has_facets"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
    registry=REGISTRY,
)

FACET_DURATION = Histogram(
    "radivault_index_facet_duration_seconds",
    "Facet GROUP BY query duration",
    ["facet_field"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    registry=REGISTRY,
)

RESULT_SIZE = Histogram(
    "radivault_index_result_size",
    "Size of items[] returned",
    ["tier"],
    buckets=(0, 1, 5, 10, 25, 50, 100, 200),
    registry=REGISTRY,
)

EMPTY_RESULT_TOTAL = Counter(
    "radivault_index_empty_result_total",
    "Requests that returned zero items",
    ["buyer_id_hash"],
    registry=REGISTRY,
)

CACHE_HIT_TOTAL = Counter(
    "radivault_index_cache_hit_total",
    "Cache hits by layer",
    ["cache_layer"],
    registry=REGISTRY,
)

RATE_LIMITED_TOTAL = Counter(
    "radivault_index_rate_limited_total",
    "Rate-limit rejections",
    ["tier", "reason"],
    registry=REGISTRY,
)

QUERY_TOO_BROAD_TOTAL = Counter(
    "radivault_index_query_too_broad_total",
    "Queries blocked by cost estimator",
    registry=REGISTRY,
)

CURSOR_FILTER_CHANGED_TOTAL = Counter(
    "radivault_index_cursor_filter_changed_total",
    "Cursor invalidated because filter sha changed",
    registry=REGISTRY,
)

AUTH_FAILURES_TOTAL = Counter(
    "radivault_index_auth_failures_total",
    "Buyer authentication failures",
    ["reason"],
    registry=REGISTRY,
)

BUILD_INFO = Counter(
    "radivault_index_build_info",
    "Build metadata (value fixed to 1)",
    ["version", "git_sha", "python_version"],
    registry=REGISTRY,
)


def init_telemetry(
    *,
    version: str,
    git_sha: str = "unknown",
    python_version: str = "unknown",
    otlp_endpoint: str | None = None,
    service_name: str = "radivault-search",
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
