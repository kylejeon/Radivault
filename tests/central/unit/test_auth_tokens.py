"""Tests for radivault_central.auth.tokens."""

from __future__ import annotations

from radivault_central.auth.tokens import (
    KID_PREFIX,
    generate_token,
    hash_token,
    parse_kid,
    verify_token,
)


def test_generate_produces_kid_prefix_and_verifies():
    bundle = generate_token()
    assert bundle.kid.startswith(KID_PREFIX)
    assert bundle.plaintext.startswith(bundle.kid + ".")
    assert verify_token(bundle.plaintext, bundle.hash)


def test_verify_rejects_wrong_plaintext():
    bundle = generate_token()
    assert not verify_token(bundle.plaintext + "x", bundle.hash)
    assert not verify_token("", bundle.hash)


def test_verify_rejects_empty_hash():
    assert not verify_token("whatever", "")


def test_parse_kid_extracts_prefix():
    bundle = generate_token()
    assert parse_kid(bundle.plaintext) == bundle.kid
    assert parse_kid(bundle.kid) == bundle.kid


def test_parse_kid_rejects_bad_values():
    assert parse_kid("") is None
    assert parse_kid("Bearer x") is None
    assert parse_kid("rvct_") is None


def test_hash_token_is_stable_for_verify():
    h = hash_token("my-token")
    assert verify_token("my-token", h)
    assert not verify_token("other", h)
