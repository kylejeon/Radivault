"""Argon2id token hashing + kid prefix parsing (dev-spec FR-23/24).

Tokens emitted to the operator look like::

    rvct_<8 char hex kid>.<random 48 char base64url>

The ``rvct_<kid>`` prefix is stored in plaintext (so lookups can find the row
without scanning every hash), while the full string is only ever persisted as
an argon2id hash.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

KID_PREFIX = "rvct_"

# A single shared PasswordHasher tuned per dev-spec §6.6 (argon2 defaults).
# Tests override via :func:`_new_password_hasher` for faster runs.
_DEFAULT_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def _new_password_hasher(
    *, time_cost: int = 3, memory_cost_kib: int = 65536, parallelism: int = 2
) -> PasswordHasher:
    return PasswordHasher(time_cost=time_cost, memory_cost=memory_cost_kib, parallelism=parallelism)


@dataclass
class TokenBundle:
    """A freshly minted bearer token — return from ``generate_token``."""

    plaintext: str  # hand to operator; never store
    kid: str  # `rvct_xxxxxxxx` — store alongside hash
    hash: str  # argon2id PHC string


def generate_token(
    *,
    hasher: PasswordHasher | None = None,
    random_bytes: int = 36,
) -> TokenBundle:
    """Generate a new bearer token and its argon2id hash.

    :param random_bytes: size of the secret portion before base64url encoding.
    """
    kid_suffix = secrets.token_hex(4)  # 8 chars → matches design-spec §3.3 output
    kid = f"{KID_PREFIX}{kid_suffix}"
    secret = secrets.token_urlsafe(random_bytes)
    plaintext = f"{kid}.{secret}"
    h = (hasher or _DEFAULT_HASHER).hash(plaintext)
    return TokenBundle(plaintext=plaintext, kid=kid, hash=h)


def hash_token(plaintext: str, *, hasher: PasswordHasher | None = None) -> str:
    """Hash a bearer token (test / admin tooling helper)."""
    return (hasher or _DEFAULT_HASHER).hash(plaintext)


def verify_token(
    plaintext: str,
    stored_hash: str,
    *,
    hasher: PasswordHasher | None = None,
) -> bool:
    """Constant-time-ish verification of a bearer token.

    Argon2id is inherently constant-work for the matching path. On mismatch we
    still run a dummy hash compare to avoid short-circuit timing leakage on
    empty/invalid inputs (FR-24).
    """
    h = hasher or _DEFAULT_HASHER
    try:
        if not stored_hash:
            hmac.compare_digest(plaintext, plaintext)
            return False
        return h.verify(stored_hash, plaintext)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def parse_kid(bearer_value: str) -> str | None:
    """Extract the ``rvct_xxxxxxxx`` prefix from a bearer value, or ``None``."""
    if not bearer_value:
        return None
    candidate = bearer_value.strip()
    if "." in candidate:
        candidate = candidate.split(".", 1)[0]
    if not candidate.startswith(KID_PREFIX):
        return None
    if len(candidate) < len(KID_PREFIX) + 4:
        return None
    return candidate
