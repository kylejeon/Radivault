"""Unit tests for keyset cursor encode/decode + filter sig (FR-25..FR-27)."""

from __future__ import annotations

import pytest

from radivault_search.query.cursor import (
    CURSOR_VERSION,
    compute_filter_sha256,
    compute_filter_sig,
    decode_cursor,
    encode_cursor,
)


def test_roundtrip_cursor() -> None:
    sig = compute_filter_sig({"modality": ["CT"]}, "date_desc")
    tok = encode_cursor(d="2026-04-20", p=12345, filter_sig=sig, sort_key="date_desc")
    cur = decode_cursor(tok)
    assert cur.v == CURSOR_VERSION
    assert cur.d == "2026-04-20"
    assert cur.p == 12345
    assert cur.s == sig
    assert cur.k == "date_desc"


def test_filter_sig_stable() -> None:
    a = compute_filter_sig({"modality": ["CT", "MR"]}, "date_desc")
    b = compute_filter_sig({"modality": ["MR", "CT"]}, "date_desc")
    # canonical_json on the caller side takes care of ordering; raw dict here
    # gives different sigs unless caller sorts — verify both paths.
    assert a != b  # raw dicts unsorted
    c = compute_filter_sig({"modality": sorted(["MR", "CT"])}, "date_desc")
    d = compute_filter_sig({"modality": sorted(["CT", "MR"])}, "date_desc")
    assert c == d


def test_sha256_hex_length() -> None:
    h = compute_filter_sha256({"modality": ["CT"]}, salt="xyz")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_decode_bad_cursor_raises() -> None:
    with pytest.raises(ValueError):
        decode_cursor("not-valid-base64!!!")
    with pytest.raises(ValueError):
        decode_cursor("")
