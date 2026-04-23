"""Unit tests for the buyer API-key primitives (dev-spec FR-2..FR-7)."""

from __future__ import annotations

from radivault_search.auth.buyer_tokens import (
    PREFIX_LIVE,
    PREFIX_TEST,
    generate_buyer_key,
    hash_buyer_key,
    parse_bearer,
    verify_buyer_key,
)


def test_generate_key_format() -> None:
    bundle = generate_buyer_key()
    assert bundle.prefix == PREFIX_LIVE
    assert bundle.plaintext.startswith(PREFIX_LIVE)
    # format: rv_live_<8 hex>_<32 alnum>
    remainder = bundle.plaintext[len(PREFIX_LIVE) :]
    kid, secret = remainder.split("_", 1)
    assert len(kid) == 8
    assert len(secret) == 32


def test_test_prefix() -> None:
    bundle = generate_buyer_key(prefix=PREFIX_TEST)
    assert bundle.plaintext.startswith(PREFIX_TEST)


def test_hash_not_plaintext() -> None:
    bundle = generate_buyer_key()
    # argon2id PHC identifier present, plaintext not embedded.
    assert bundle.hash.startswith("$argon2id$")
    assert bundle.plaintext not in bundle.hash


def test_verify_ok_and_reject() -> None:
    bundle = generate_buyer_key()
    assert verify_buyer_key(bundle.plaintext, bundle.hash) is True
    assert verify_buyer_key(bundle.plaintext + "x", bundle.hash) is False


def test_parse_bearer_ok() -> None:
    bundle = generate_buyer_key()
    parsed = parse_bearer(bundle.plaintext)
    assert parsed is not None
    kid, prefix = parsed
    assert prefix == PREFIX_LIVE
    assert len(kid) == 8


def test_parse_bearer_test_prefix_gated() -> None:
    bundle = generate_buyer_key(prefix=PREFIX_TEST)
    assert parse_bearer(bundle.plaintext) is None
    assert parse_bearer(bundle.plaintext, allow_test_prefix=True) is not None


def test_parse_bearer_format_fail() -> None:
    assert parse_bearer("") is None
    assert parse_bearer("rv_live_short") is None
    assert parse_bearer("rv_live_ZZZZZZZZ_x" * 3) is None  # kid not hex
    # wrong secret length
    assert parse_bearer("rv_live_abcd1234_onlyonesecret") is None


def test_hash_function_reuse() -> None:
    h = hash_buyer_key("rv_live_abcd1234_" + "x" * 32)
    assert h.startswith("$argon2id$")
