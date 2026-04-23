"""Error taxonomy — envelopes carry correct codes/HTTP statuses."""

from __future__ import annotations

import pytest

from radivault_fulfillment.errors import (
    AuthUnavailable,
    AuthWrongPlane,
    JobCounterRegress,
    JobLeaseExpired,
    JobLeaseOwnership,
    OrderExpired,
    OrderNotFound,
    OrderNotReady,
    OrderQuotaExceeded,
    OrderScopeForbidden,
    OrderStateTransition,
    OrderTerminal,
    OrderTierExceeded,
    OrderTooLarge,
    UrlMintFailed,
    UrlMintRate,
    UrlTtlExceeded,
)


@pytest.mark.parametrize(
    "exc_cls,expected_status,expected_code",
    [
        (AuthWrongPlane, 401, "ERR_AUTH_WRONG_PLANE"),
        (AuthUnavailable, 503, "ERR_AUTH_UNAVAILABLE"),
        (OrderScopeForbidden, 403, "ERR_ORDER_SCOPE_FORBIDDEN"),
        (OrderTierExceeded, 422, "ERR_ORDER_TIER_EXCEEDED"),
        (OrderQuotaExceeded, 429, "ERR_ORDER_QUOTA_EXCEEDED"),
        (OrderTooLarge, 413, "ERR_ORDER_TOO_LARGE"),
        (OrderStateTransition, 409, "ERR_ORDER_STATE_TRANSITION"),
        (OrderNotReady, 409, "ERR_ORDER_NOT_READY"),
        (OrderExpired, 410, "ERR_ORDER_EXPIRED"),
        (OrderTerminal, 410, "ERR_ORDER_TERMINAL"),
        (OrderNotFound, 404, "ERR_ORDER_NOT_FOUND"),
        (UrlTtlExceeded, 422, "ERR_URL_TTL_EXCEEDED"),
        (UrlMintRate, 429, "ERR_URL_MINT_RATE"),
        (UrlMintFailed, 502, "ERR_URL_MINT_FAILED"),
        (JobLeaseOwnership, 403, "ERR_JOB_LEASE_OWNERSHIP"),
        (JobLeaseExpired, 409, "ERR_JOB_LEASE_EXPIRED"),
        (JobCounterRegress, 400, "ERR_JOB_COUNTER_REGRESS"),
    ],
)
def test_error_envelope_shape(exc_cls, expected_status, expected_code) -> None:
    exc = exc_cls()
    env = exc.to_envelope("req_test")
    assert exc.status_code == expected_status
    assert env["error"] == expected_code
    assert env["request_id"] == "req_test"
    assert env["message_en"]
    assert env["message_ko"]
    assert env["doc_url"].endswith(f"/{expected_code}")
