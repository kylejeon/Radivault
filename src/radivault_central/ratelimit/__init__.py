"""Slowapi-based rate limit middleware (dev-spec FR-43..FR-45)."""

from __future__ import annotations

from radivault_central.ratelimit.middleware import RateLimitMiddleware, hospital_key

__all__ = ["RateLimitMiddleware", "hospital_key"]
