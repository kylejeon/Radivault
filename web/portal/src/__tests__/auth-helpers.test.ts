/**
 * Unit tests for the buyer-auth primitive helpers (dev-spec FR-AUTH-3,
 * FR-AUTH-2, FR-AUTH-6, FR-AUTH-8).
 */

import { describe, it, expect } from "vitest";

import {
  hashPassword,
  verifyPassword,
  ARGON2_PARAMS,
  TIMING_SAFE_DUMMY_HASH,
} from "@/lib/auth/argon2";
import {
  generateOtp,
  hashOtp,
  compareOtpHash,
  generateResetToken,
  hashResetToken,
} from "@/lib/auth/otp";
import { mintApiKey, maskApiKey, maskKid } from "@/lib/auth/api-key";

describe("argon2", () => {
  it("hashes a password to a PHC string with the OWASP parameters", async () => {
    const hash = await hashPassword("correct-horse-battery-staple");
    // PHC format: $argon2id$v=19$m=19456,t=2,p=1$<salt>$<hash>
    expect(hash).toMatch(/^\$argon2id\$v=19\$m=19456,t=2,p=1\$/);
    expect(ARGON2_PARAMS.memoryCost).toBe(19_456);
  });

  it("verifies the correct password", async () => {
    const hash = await hashPassword("hunter2-no-not-really");
    expect(await verifyPassword(hash, "hunter2-no-not-really")).toBe(true);
  });

  it("rejects the wrong password", async () => {
    const hash = await hashPassword("correct-password");
    expect(await verifyPassword(hash, "wrong-password")).toBe(false);
  });

  it("rejects empty inputs without throwing", async () => {
    expect(await verifyPassword("", "anything")).toBe(false);
    expect(await verifyPassword("garbage", "")).toBe(false);
  });

  it("treats malformed PHC strings as failed verification (no throw)", async () => {
    expect(await verifyPassword("not-a-phc-string", "password")).toBe(false);
  });

  it("bounds the plaintext at 1 KiB", async () => {
    const huge = "x".repeat(1025);
    await expect(hashPassword(huge)).rejects.toThrow(/1 KiB/);
  });

  it("exposes a non-empty timing-safe dummy hash", () => {
    expect(TIMING_SAFE_DUMMY_HASH.length).toBeGreaterThan(0);
    expect(TIMING_SAFE_DUMMY_HASH).toMatch(/^\$argon2id\$/);
  });
});

describe("otp", () => {
  it("generates a 6-digit zero-padded code", () => {
    for (let i = 0; i < 200; i++) {
      const code = generateOtp();
      expect(code).toMatch(/^\d{6}$/);
    }
  });

  it("hashes deterministically per (otp, buyerPk)", () => {
    const a = hashOtp("123456", 42);
    const b = hashOtp("123456", 42);
    const c = hashOtp("123456", 99);
    expect(a).toBe(b);
    expect(a).not.toBe(c);
  });

  it("compareOtpHash is constant-time and equality-safe", () => {
    const stored = hashOtp("999999", 7);
    expect(compareOtpHash(hashOtp("999999", 7), stored)).toBe(true);
    expect(compareOtpHash(hashOtp("999998", 7), stored)).toBe(false);
  });

  it("generateResetToken is 32-byte base64url (43 chars no padding)", () => {
    const token = generateResetToken();
    expect(token).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(token.length).toBeGreaterThanOrEqual(43);
  });

  it("hashResetToken is deterministic SHA-256 hex", () => {
    const t = generateResetToken();
    expect(hashResetToken(t)).toMatch(/^[a-f0-9]{64}$/);
    expect(hashResetToken(t)).toBe(hashResetToken(t));
  });
});

describe("api-key", () => {
  it("mints a 56-char rv_live_… plaintext + 16-char kid + sha256 hash", () => {
    const k = mintApiKey();
    expect(k.plaintext).toMatch(/^rv_live_[A-Za-z0-9_-]{40,}$/);
    expect(k.kid).toBe(k.plaintext.slice(0, 16));
    expect(k.kid.startsWith("rv_live_")).toBe(true);
    expect(k.tokenHash).toMatch(/^[a-f0-9]{64}$/);
  });

  it("maskApiKey renders Stripe-style rv_live_<first4>…<last4>", () => {
    const k = mintApiKey();
    const masked = maskApiKey(k.plaintext);
    expect(masked).toMatch(/^rv_live_[A-Za-z0-9_-]{4}…[A-Za-z0-9_-]{4}$/);
  });

  it("maskKid appends ellipsis", () => {
    expect(maskKid("rv_live_K8dF7sX9")).toBe("rv_live_K8dF7sX9…");
  });
});
