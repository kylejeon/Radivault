"""Idempotency middleware — key validation + replay."""

from __future__ import annotations

import pytest

from radivault_fulfillment.errors import IdempFormat, IdempMissing
from radivault_fulfillment.idempotency.middleware import (
    IdempotencyKeyValidator,
    _requires_idempotency,
)


def test_validate_missing_raises():
    with pytest.raises(IdempMissing):
        IdempotencyKeyValidator.validate(None)


def test_validate_too_short():
    with pytest.raises(IdempFormat):
        IdempotencyKeyValidator.validate("tooshort")


def test_validate_bad_chars():
    with pytest.raises(IdempFormat):
        IdempotencyKeyValidator.validate("bad chars with spaces and $$$$")


def test_validate_ok():
    out = IdempotencyKeyValidator.validate("01HX12345ABCDEFG")
    assert out == "01HX12345ABCDEFG"


@pytest.mark.parametrize(
    "method,path,expected",
    [
        ("POST", "/v1/orders", True),
        ("POST", "/v1/orders/ord_01/cancel", True),
        ("POST", "/v1/gateway/transfer-jobs/tj_01/progress", True),
        ("POST", "/v1/gateway/transfer-jobs/tj_01/complete", True),
        ("POST", "/v1/gateway/transfer-jobs/tj_01/fail", True),
        ("GET", "/v1/orders", False),
        ("GET", "/v1/orders/ord_01", False),
        ("POST", "/v1/orders/ord_01/download-urls", False),
    ],
)
def test_requires_idempotency_rules(method, path, expected):
    """Use a minimal duck-typed request object."""

    class R:
        def __init__(self, m, p):
            self.method = m

            class U:
                path = p

            self.url = U()

    assert _requires_idempotency(R(method, path)) is expected
