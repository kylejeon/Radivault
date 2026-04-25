/**
 * Email OTP + password-reset token primitives (dev-spec-buyer-auth
 * FR-AUTH-2, FR-AUTH-6).
 *
 * Storage rule: only the SHA-256 hash of the OTP / token is persisted.
 * Plaintext is generated, returned to the caller for delivery (email or
 * stdout), then dropped from memory.
 */

import { randomBytes, randomInt, createHash, timingSafeEqual } from "node:crypto";

/**
 * Generate a 6-digit zero-padded OTP code (000000 .. 999999).
 *
 * Uses ``crypto.randomInt`` for uniform distribution. The 1e6 ceiling means
 * each code carries ~19.9 bits of entropy — adequate when paired with the
 * 3-attempts-per-row lockout (FR-AUTH-2).
 */
export function generateOtp(): string {
  return String(randomInt(0, 1_000_000)).padStart(6, "0");
}

/**
 * Hash an OTP for at-rest storage. Salt is the buyer_pk so a stolen DB
 * dump can't be brute-forced by precomputing a 1e6 rainbow table.
 */
export function hashOtp(otp: string, buyerPk: string | number): string {
  const salt = String(buyerPk);
  return createHash("sha256").update(`${otp}:${salt}`).digest("hex");
}

/**
 * Constant-time compare of a freshly hashed OTP attempt against the stored
 * hash. We use ``timingSafeEqual`` over hex buffers of identical length
 * (SHA-256 = 32 bytes = 64 hex chars).
 */
export function compareOtpHash(provided: string, stored: string): boolean {
  if (provided.length !== stored.length) return false;
  const a = Buffer.from(provided, "hex");
  const b = Buffer.from(stored, "hex");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

/**
 * Generate a 32-byte base64url password-reset token (FR-AUTH-6).
 *
 * 256 bits of entropy, safe to put in a URL query string.
 */
export function generateResetToken(): string {
  return randomBytes(32).toString("base64url");
}

/**
 * Hash a reset token for storage. No per-buyer salt because the table has
 * a UNIQUE constraint on ``token_hash`` — we lookup *by* the hash.
 */
export function hashResetToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}
