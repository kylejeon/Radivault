"""Keyset cursor encode/decode + filter_sha256 binding (dev-spec §4.4).

Cursor internal shape (dev-spec FR-25)::

    {
      "v": 1,                    # cursor schema version
      "d": "2026-04-18",          # study_date_shifted OR ingested_at ISO
      "p": 12345,                 # study_pk
      "s": "YbM3z7K9QaP1",        # sha256(canonical_filter||sort_key)[:12] b64url
      "k": "date_desc"            # sort_key
    }

Encoded as base64url (no padding) JSON string.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any

CURSOR_VERSION = 1


@dataclass
class Cursor:
    v: int
    d: str
    p: int
    s: str
    k: str


def compute_filter_sig(filter_dict: dict[str, Any], sort_key: str) -> str:
    """Return the 12-char base64url sha256 hash tying a cursor to its filter."""
    canonical = json.dumps(filter_dict, sort_keys=True, separators=(",", ":"))
    raw = hashlib.sha256((canonical + "|" + sort_key).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(raw)[:12].decode("ascii").rstrip("=")


def compute_filter_sha256(filter_dict: dict[str, Any], *, salt: str = "") -> str:
    """Return the full 64-char hex sha256 for the audit trail (FR-53)."""
    canonical = json.dumps(filter_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((canonical + salt).encode("utf-8")).hexdigest()


def encode_cursor(
    *,
    d: str,
    p: int,
    filter_sig: str,
    sort_key: str,
) -> str:
    payload: dict[str, Any] = {
        "v": CURSOR_VERSION,
        "d": d,
        "p": p,
        "s": filter_sig,
        "k": sort_key,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: str) -> Cursor:
    """Decode a cursor token. Raises ``ValueError`` on malformed input."""
    if not token:
        raise ValueError("empty cursor")
    pad = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
    except Exception as exc:
        raise ValueError(f"invalid base64: {exc}") from exc
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise ValueError(f"invalid json: {exc}") from exc
    try:
        return Cursor(
            v=int(data["v"]), d=str(data["d"]), p=int(data["p"]), s=str(data["s"]), k=str(data["k"])
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"missing field: {exc}") from exc
