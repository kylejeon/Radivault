/**
 * MemoryAuthStore behaviour tests (dev-spec FR-AUTH-1..11).
 */

import { describe, it, expect, beforeEach } from "vitest";

import { getAuthStore, AuthStoreError } from "@/lib/auth/store";

const sampleArgs = {
  email: "alice@acme.ai",
  passwordHash: "$argon2id$v=19$m=19456,t=2,p=1$ZGVtb19zYWx0$ZGVtb19oYXNo",
  organization: "Acme",
  displayName: "Acme",
  intent: "commercial-ai" as const,
  country: null,
  marketingEmailOptIn: false,
  pipaConsents: {},
  consentTermsVersion: "tos-v1.0;privacy-v1.0",
  apiKeyKid: "rv_live_K8dF7sX9",
  apiKeyTokenHash: "deadbeef".repeat(8),
  skipEmailVerify: true,
};

describe("MemoryAuthStore", () => {
  beforeEach(() => {
    getAuthStore().reset();
  });

  it("creates a buyer + credentials + apiKey atomically", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    expect(out.buyer.buyerPk).toBe(1);
    expect(out.buyer.buyerId).toMatch(/^buy_/);
    expect(out.credentials.email).toBe("alice@acme.ai");
    expect(out.credentials.emailVerifiedAt).not.toBeNull(); // skip-flag true
    expect(out.apiKey.kid).toBe("rv_live_K8dF7sX9");
  });

  it("throws ERR_EMAIL_TAKEN on duplicate email", async () => {
    const store = getAuthStore();
    await store.createBuyerWithCredentials(sampleArgs);
    await expect(store.createBuyerWithCredentials(sampleArgs)).rejects.toBeInstanceOf(
      AuthStoreError,
    );
  });

  it("findCredentialsByEmail is case-insensitive (citext-equivalent)", async () => {
    const store = getAuthStore();
    await store.createBuyerWithCredentials(sampleArgs);
    expect(await store.findCredentialsByEmail("ALICE@ACME.AI")).not.toBeNull();
  });

  it("bumps session_version on call", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    const v = await store.bumpSessionVersion(out.buyer.buyerPk);
    expect(v).toBe(2);
  });

  it("rotateApiKey revokes the old key and inserts a fresh active one", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    const fresh = await store.rotateApiKey(
      out.buyer.buyerPk,
      "rv_live_NEW1NEW1",
      "newhash".repeat(8),
    );
    const active = await store.findActiveApiKey(out.buyer.buyerPk);
    expect(active?.kid).toBe(fresh.kid);
    expect(active?.kid).not.toBe(out.apiKey.kid);
  });

  it("revokeApiKey leaves no active keys", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    await store.revokeApiKey(out.buyer.buyerPk);
    const active = await store.findActiveApiKey(out.buyer.buyerPk);
    expect(active).toBeNull();
  });

  it("OTP attempt counter caps at 3 then invalidates", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    const otp = await store.insertOtp(
      out.buyer.buyerPk,
      "hash",
      Date.now() + 600_000,
    );
    expect(await store.bumpOtpAttempts(otp.id)).toBe(1);
    expect(await store.bumpOtpAttempts(otp.id)).toBe(2);
    expect(await store.bumpOtpAttempts(otp.id)).toBe(3);
    await store.invalidateOtp(otp.id);
    expect(await store.findActiveOtp(out.buyer.buyerPk)).toBeNull();
  });

  it("password-reset token is one-shot", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    const t = await store.insertResetToken(
      out.buyer.buyerPk,
      "tokenhash1",
      Date.now() + 3_600_000,
    );
    expect(await store.findActiveResetTokenByHash("tokenhash1")).not.toBeNull();
    await store.markResetTokenUsed(t.id);
    expect(await store.findActiveResetTokenByHash("tokenhash1")).toBeNull();
  });

  it("soft delete blocks 30-day re-signup with the same email", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    await store.softDeleteBuyer(out.buyer.buyerPk);
    expect(await store.isEmailRecentlyDeleted("alice@acme.ai", 30 * 24 * 3600 * 1000)).toBe(
      true,
    );
    // After 31 days the grace expires (simulate via 0-window check).
    expect(await store.isEmailRecentlyDeleted("alice@acme.ai", 0)).toBe(false);
    // existing credentials row no longer surfaces by the original email
    expect(await store.findCredentialsByEmail("alice@acme.ai")).toBeNull();
    // and all keys are revoked
    expect(await store.findActiveApiKey(out.buyer.buyerPk)).toBeNull();
  });

  it("audit events are recorded and queryable by type", async () => {
    const store = getAuthStore();
    const out = await store.createBuyerWithCredentials(sampleArgs);
    await store.insertEvent({ buyerPk: out.buyer.buyerPk, eventType: "signup" });
    await store.insertEvent({ buyerPk: out.buyer.buyerPk, eventType: "signin" });
    await store.insertEvent({ buyerPk: out.buyer.buyerPk, eventType: "signin" });
    expect(await store.countEventsByType("signup")).toBe(1);
    expect(await store.countEventsByType("signin")).toBe(2);
    const events = await store.listEventsForBuyer(out.buyer.buyerPk);
    expect(events.length).toBeGreaterThanOrEqual(3);
  });
});
