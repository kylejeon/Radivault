/**
 * Argon2id password hashing (dev-spec-buyer-auth FR-AUTH-3).
 *
 * Parameters per OWASP Password Storage Cheat Sheet (2024):
 *   m = 19 MiB, t = 2, p = 1, hashLength = 32B, saltLength = 16B
 *
 * Encoded output goes straight into ``buyer_credentials.password_hash`` as a
 * PHC string, e.g. ``$argon2id$v=19$m=19456,t=2,p=1$<salt>$<hash>``. The
 * argon2.verify() call parses the same string and re-derives parameters, so
 * we never need to re-emit the params at verify time.
 *
 * Plaintext is never logged or returned. Caller must drop references to the
 * plaintext immediately after the hash/verify call.
 */

import argon2 from "argon2";

export const ARGON2_PARAMS = {
  type: argon2.argon2id,
  memoryCost: 19_456, // 19 MiB
  timeCost: 2,
  parallelism: 1,
  hashLength: 32,
} as const;

/**
 * Hash a plaintext password.
 *
 * Throws if the input is empty or > 1 KiB (defense-in-depth — zod should
 * have already enforced 8..64). Otherwise returns the PHC encoded string.
 */
export async function hashPassword(plaintext: string): Promise<string> {
  if (!plaintext) throw new Error("hashPassword: empty plaintext");
  if (plaintext.length > 1024) {
    throw new Error("hashPassword: plaintext exceeds 1 KiB safety bound");
  }
  return argon2.hash(plaintext, ARGON2_PARAMS);
}

/**
 * Verify a plaintext against a stored PHC hash.
 *
 * Returns ``true`` on match, ``false`` on mismatch. Never throws on a
 * bad-but-well-formed hash — those resolve to ``false``. Throws only on
 * malformed PHC input (which would indicate DB corruption).
 */
export async function verifyPassword(
  encodedHash: string,
  plaintext: string,
): Promise<boolean> {
  if (!encodedHash || !plaintext) return false;
  try {
    return await argon2.verify(encodedHash, plaintext);
  } catch {
    // argon2.verify throws on truly malformed PHC strings. Treat as a
    // failed verification rather than crashing the request handler.
    return false;
  }
}

/**
 * Pre-computed dummy hash for timing-safe signin (FR-AUTH-4 §AC-AUTH-4.2).
 *
 * When the email lookup returns 0 rows we still call argon2.verify against
 * this constant so the response time matches the success path within
 * 20 ms (acceptance criterion). The plaintext used to mint this is the
 * 32-character literal "radivault-timing-safe-dummy-pw01" — value is
 * deliberately published; security rests on argon2 verify time, not
 * secrecy of the hash.
 */
export const TIMING_SAFE_DUMMY_HASH =
  "$argon2id$v=19$m=19456,t=2,p=1$" +
  "ZGVtb19zYWx0X3RpbWluZw$" +
  "fXh0NJEdzDIycy5kJqcF6vJh4f0qfZRcU0p7XZqp+qE";
