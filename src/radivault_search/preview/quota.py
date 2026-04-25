"""Per-buyer daily sample-download quota — Redis fixed window.

Q-6 default (dev-spec-buyer-browse-preview §14): use Redis with key

    quota:{buyer_pk}:{YYYYMMDD}      INTEGER, EXPIRE 86400 sec

Reset semantics: TTL 86400 from first INCR. Calendar-day reset is
captured in ``resets_at_iso`` returned from :func:`incr_and_check`,
which always reflects the next 00:00 KST boundary so the UI can render
"Resets at 00:00 KST" without computing it client-side.

Failure modes
-------------
- Redis unreachable → :class:`QuotaUnavailable` (caller maps to 503,
  matching ratelimit ``ERR_IDEMP_UNAVAILABLE`` behaviour).
- Quota exceeded → :class:`QuotaExceeded` with ``retry_after_seconds``
  set to whatever ``EXPIRE`` reports (or seconds-to-midnight as a
  fallback) so the caller can echo ``Retry-After`` and the UI can show
  the reset countdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# KST = UTC+9, fixed offset (no DST in Korea). Use a constant tz so the
# reset-at calculation is stable on every host regardless of system TZ.
_KST = timezone(timedelta(hours=9))


class QuotaUnavailable(RuntimeError):
    """Raised when the Redis backend is unreachable."""


class QuotaExceeded(RuntimeError):
    """Raised when the buyer has hit the daily limit."""

    def __init__(self, *, retry_after_seconds: int, resets_at_iso: str) -> None:
        super().__init__("daily sample download quota exceeded")
        self.retry_after_seconds = retry_after_seconds
        self.resets_at_iso = resets_at_iso


@dataclass
class QuotaState:
    used: int
    limit: int
    resets_at_iso: str  # ISO 8601 in KST


def _kst_today_key(buyer_pk: int) -> tuple[str, str]:
    """Return ``(redis_key, yyyymmdd)`` rooted at today's KST date."""
    now_kst = datetime.now(tz=_KST)
    yyyymmdd = now_kst.strftime("%Y%m%d")
    return f"quota:{buyer_pk}:{yyyymmdd}", yyyymmdd


def _seconds_to_kst_midnight() -> int:
    now_kst = datetime.now(tz=_KST)
    tomorrow_kst = (now_kst + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = tomorrow_kst - now_kst
    # Always at least 1 to avoid Retry-After: 0 surprises.
    return max(1, int(delta.total_seconds()))


def _next_kst_midnight_iso() -> str:
    now_kst = datetime.now(tz=_KST)
    tomorrow_kst = (now_kst + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return tomorrow_kst.isoformat()


def peek(redis_client, buyer_pk: int, *, daily_limit: int = 1) -> QuotaState:
    """Read-only quota inspection — does NOT increment.

    Used by the UI to render "Today: N/limit" without consuming a slot.
    """
    if redis_client is None:
        raise QuotaUnavailable("redis client unavailable")
    key, _ = _kst_today_key(buyer_pk)
    try:
        raw = redis_client.get(key)
    except Exception as exc:  # noqa: BLE001
        raise QuotaUnavailable(f"redis get failed: {exc}") from exc
    used = int(raw) if raw is not None else 0
    return QuotaState(used=used, limit=daily_limit, resets_at_iso=_next_kst_midnight_iso())


def incr_and_check(
    redis_client, buyer_pk: int, *, daily_limit: int = 1
) -> QuotaState:
    """Atomically increment + check + set TTL.

    Raises :class:`QuotaExceeded` if the post-INCR value exceeds the
    daily limit, in which case the caller should NOT proceed with the
    sample-download. The increment is left in place so two concurrent
    requests cannot both succeed (last-writer wins is acceptable —
    quota of 1 means the second request always loses).
    """
    if redis_client is None:
        raise QuotaUnavailable("redis client unavailable")
    key, _ = _kst_today_key(buyer_pk)
    try:
        new_value = int(redis_client.incr(key))
        # Set TTL only on the first INCR (when value just became 1) so
        # we don't keep extending the window on every increment. EXPIRE
        # is idempotent enough that calling on every INCR would also be
        # OK — but conditional makes the reset semantics crisper.
        if new_value == 1:
            try:
                redis_client.expire(key, 86400)
            except Exception:  # noqa: BLE001 — keep going, TTL retry below
                pass
        else:
            # Belt-and-braces: re-apply EXPIRE if no TTL was ever set
            # (e.g. operator MULTI without EXEC) so the key cannot leak
            # forever.
            try:
                ttl = int(redis_client.ttl(key))
                if ttl < 0:
                    redis_client.expire(key, 86400)
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        raise QuotaUnavailable(f"redis incr failed: {exc}") from exc

    if new_value > daily_limit:
        raise QuotaExceeded(
            retry_after_seconds=_seconds_to_kst_midnight(),
            resets_at_iso=_next_kst_midnight_iso(),
        )
    return QuotaState(
        used=new_value, limit=daily_limit, resets_at_iso=_next_kst_midnight_iso()
    )


__all__ = [
    "QuotaExceeded",
    "QuotaState",
    "QuotaUnavailable",
    "incr_and_check",
    "peek",
]
