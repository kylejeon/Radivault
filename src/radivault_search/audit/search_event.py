"""Append-only writer for ``search_audit`` (dev-spec §4.10, FR-51..FR-55).

Inserts are fire-and-forget from the router's perspective; FastAPI's
``BackgroundTasks`` dispatches them after the response is returned so
search latency is unaffected.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from radivault_search.db.repository import insert_search_audit

log = logging.getLogger("radivault_search.audit")


def write_audit(
    session_factory: Callable,
    *,
    buyer_pk: int,
    kid: str,
    endpoint: str,
    filter_sha256: str | None,
    filter_json_sha256: str | None,
    result_count: int | None,
    cache_hit: bool,
    status_code: int,
    error_code: str | None,
    latency_ms: int,
    request_id: str,
    cursor_presence: bool,
    raw_query: str | None = None,
    masked_query: str | None = None,
    phi_flagged_patterns: list[str] | None = None,
) -> None:
    """Insert one row into ``search_audit`` in its own session.

    Errors are logged but never propagated — the audit writer is best-effort
    and must never fail a successful search response.

    text-search-description FR-TS-10 additions: ``raw_query`` /
    ``masked_query`` / ``phi_flagged_patterns`` are forwarded to the
    repository when the buyer used the free-text search bar.
    """
    try:
        with session_factory() as session:
            insert_search_audit(
                session,
                buyer_pk=buyer_pk,
                kid=kid,
                endpoint=endpoint,
                filter_sha256=filter_sha256,
                filter_json_sha256=filter_json_sha256,
                result_count=result_count,
                cache_hit=cache_hit,
                status_code=status_code,
                error_code=error_code,
                latency_ms=latency_ms,
                request_id=request_id,
                cursor_presence=cursor_presence,
                raw_query=raw_query,
                masked_query=masked_query,
                phi_flagged_patterns=phi_flagged_patterns,
            )
    except Exception:  # pragma: no cover — defensive
        log.exception(
            "search_audit_write_failed",
            extra={"event": "audit.write.fail", "request_id": request_id},
        )
