"""Idempotency-Key validator (FR-28)."""

from __future__ import annotations

import pytest

from radivault_central.errors import IdempFormat, IdempMissing
from radivault_central.idempotency.middleware import IdempotencyKeyValidator


def test_validate_accepts_reasonable_key():
    assert (
        IdempotencyKeyValidator.validate("01HXX8WQ9Z3K7V5B2A1N6P4R9T")
        == "01HXX8WQ9Z3K7V5B2A1N6P4R9T"
    )


def test_validate_missing_key():
    with pytest.raises(IdempMissing):
        IdempotencyKeyValidator.validate(None)
    with pytest.raises(IdempMissing):
        IdempotencyKeyValidator.validate("")


def test_validate_rejects_bad_format():
    with pytest.raises(IdempFormat):
        IdempotencyKeyValidator.validate("too-short")  # <16
    with pytest.raises(IdempFormat):
        IdempotencyKeyValidator.validate("x" * 200)  # >128
    with pytest.raises(IdempFormat):
        IdempotencyKeyValidator.validate("invalid chars!@#" + "0" * 10)
