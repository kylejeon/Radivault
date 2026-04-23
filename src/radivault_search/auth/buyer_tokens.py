"""Buyer API-key format + argon2id hashing (dev-spec §4.1 FR-2..FR-7).

Token format: ``rv_live_<kid8>_<random32>`` — total 48 characters.

``rv_test_`` prefix is allowed in dev/stage via the ``RV_SEARCH_ENV`` env var
(FR-2). Both prefixes produce an 8-char ``kid`` (lowercase alphanumerics from
``secrets.token_hex(4)``) and a 32-char ``secret`` (``secrets.token_urlsafe``
trimmed — chosen from ``[a-zA-Z0-9]`` to preserve the fixed 48-char length).

``token_hash`` is argon2id with params matching central-ingest.
"""

from __future__ import annotations

import contextlib
import hmac
import secrets
import string
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

PREFIX_LIVE = "rv_live_"
PREFIX_TEST = "rv_test_"
KID_LEN = 8
SECRET_LEN = 32

# Accept both live and test prefixes; caller gates by env (FR-2).
_ALLOWED_PREFIXES = (PREFIX_LIVE, PREFIX_TEST)

# Secret alphabet — base62 so the string is always exactly 32 chars and never
# contains ``_`` or ``-`` (reserves ``_`` as the one separator in the token).
_SECRET_ALPHABET = string.ascii_letters + string.digits

_DEFAULT_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

# Pre-computed dummy hash used when a key can't be found — lets us spend the
# same argon2 CPU on miss vs hit (FR-7 constant-ish time).
_DUMMY_HASH = _DEFAULT_HASHER.hash("rv_live_00000000_" + "x" * SECRET_LEN)


def _new_password_hasher(
    *,
    time_cost: int = 3,
    memory_cost_kib: int = 65536,
    parallelism: int = 2,
) -> PasswordHasher:
    return PasswordHasher(time_cost=time_cost, memory_cost=memory_cost_kib, parallelism=parallelism)


@dataclass
class BuyerKeyBundle:
    plaintext: str  # full key, hand to buyer — never store
    kid: str  # 8-char alnum, unique; store in DB
    hash: str  # argon2id PHC string
    prefix: str  # 'rv_live_' or 'rv_test_'


def generate_buyer_key(
    *,
    hasher: PasswordHasher | None = None,
    prefix: str = PREFIX_LIVE,
) -> BuyerKeyBundle:
    """Mint a fresh buyer key and its argon2id hash."""
    if prefix not in _ALLOWED_PREFIXES:
        raise ValueError(f"invalid prefix: {prefix}")
    kid = secrets.token_hex(KID_LEN // 2)  # 8 hex chars
    secret = "".join(secrets.choice(_SECRET_ALPHABET) for _ in range(SECRET_LEN))
    plaintext = f"{prefix}{kid}_{secret}"
    h = (hasher or _DEFAULT_HASHER).hash(plaintext)
    return BuyerKeyBundle(plaintext=plaintext, kid=kid, hash=h, prefix=prefix)


def hash_buyer_key(plaintext: str, *, hasher: PasswordHasher | None = None) -> str:
    return (hasher or _DEFAULT_HASHER).hash(plaintext)


def verify_buyer_key(
    plaintext: str,
    stored_hash: str,
    *,
    hasher: PasswordHasher | None = None,
) -> bool:
    """Constant-time-ish verification.

    On any failure path we still spend an argon2 compare on a dummy hash so a
    missing/invalid input path takes roughly the same wall-time as a hit
    (FR-7).
    """
    h = hasher or _DEFAULT_HASHER
    try:
        if not stored_hash:
            # Dummy compare so empty-hash path still spends CPU.
            with contextlib.suppress(Exception):
                h.verify(_DUMMY_HASH, plaintext or "invalid")
            hmac.compare_digest(plaintext, plaintext)
            return False
        return h.verify(stored_hash, plaintext)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def constant_time_miss(plaintext: str, *, hasher: PasswordHasher | None = None) -> None:
    """Spend one argon2 compare against a dummy hash (FR-7).

    Used when the ``kid`` is not in the DB so the response time is similar
    to the hit path.
    """
    h = hasher or _DEFAULT_HASHER
    try:
        h.verify(_DUMMY_HASH, plaintext or "invalid")
    except Exception:
        return


def parse_bearer(
    bearer_value: str,
    *,
    allow_test_prefix: bool = False,
) -> tuple[str, str] | None:
    """Split a bearer token into ``(kid, prefix)`` or return ``None``.

    Returns ``None`` on any format violation so callers map to
    ``ERR_AUTH_FORMAT``.
    """
    if not bearer_value:
        return None
    v = bearer_value.strip()
    allowed = [PREFIX_LIVE] + ([PREFIX_TEST] if allow_test_prefix else [])
    prefix = next((p for p in allowed if v.startswith(p)), None)
    if prefix is None:
        return None
    remainder = v[len(prefix) :]
    # Must be <kid8>_<secret32>
    parts = remainder.split("_", 1)
    if len(parts) != 2:
        return None
    kid, secret = parts
    if len(kid) != KID_LEN or not all(c in string.hexdigits for c in kid):
        return None
    if len(secret) != SECRET_LEN:
        return None
    if not all(c in _SECRET_ALPHABET for c in secret):
        return None
    return (kid, prefix)


__all__ = [
    "KID_LEN",
    "PREFIX_LIVE",
    "PREFIX_TEST",
    "SECRET_LEN",
    "BuyerKeyBundle",
    "constant_time_miss",
    "generate_buyer_key",
    "hash_buyer_key",
    "parse_bearer",
    "verify_buyer_key",
]
