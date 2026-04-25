/**
 * Auth store abstraction (dev-spec-buyer-auth FR-AUTH-1..12).
 *
 * Why an abstraction: the portal today is a pure BFF — no direct Postgres
 * client. Wiring ``pg`` end-to-end (connection pool, migrations, prepared
 * statements, retry semantics) is a meaningful infra surface that we
 * deliberately defer to v0.1.1 (planner Q10 = in-memory rate limit
 * established the same boundary).
 *
 * For v0.1 (D-13 demo) we ship a process-local in-memory store. It is
 * fully functional: signup → signin → OTP → password-reset → revoke all
 * persist for the lifetime of the Next.js process. Acceptance tests run
 * against the same store.
 *
 * The Postgres backend ships as a SQL bootstrap file
 * (``scripts/demo_setup/bootstrap_buyer_auth.sql``) so the production DDL
 * is already written and reviewed; only the runtime client wiring is
 * deferred. When ``BUYER_AUTH_STORE=postgres`` is added the same
 * ``AuthStore`` interface here becomes the integration point with zero
 * call-site changes.
 */

import { randomBytes } from "node:crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Buyer = {
  buyerPk: number; // matches deployed BIGSERIAL
  buyerId: string; // public id, e.g. "buy_K8dF7sX9"
  displayName: string;
  organization: string;
  intent: "research" | "commercial-ai" | "clinical-trial" | "other";
  country: string | null;
  contactEmail: string;
  tier: "preview" | "paid";
  active: boolean;
  enrolledAt: number;
};

export type BuyerCredentials = {
  buyerPk: number;
  email: string; // citext lowercased
  passwordHash: string;
  emailVerifiedAt: number | null;
  marketingEmailOptIn: boolean;
  sessionVersion: number;
  pipaConsents: Record<string, string | null>;
  consentTermsVersion: string;
  deletedAt: number | null;
  createdAt: number;
  updatedAt: number;
};

export type ApiKey = {
  kid: string; // 'rv_live_K8dF7sX9' (first 16 chars of plaintext)
  buyerPk: number;
  tokenHash: string; // SHA-256(plaintext)
  label: string;
  tier: "preview" | "paid";
  createdAt: number;
  lastUsedAt: number | null;
  revokedAt: number | null;
};

export type Otp = {
  id: number;
  buyerPk: number;
  otpHash: string;
  expiresAt: number;
  attempts: number;
  consumedAt: number | null;
  createdAt: number;
};

export type ResetToken = {
  id: number;
  buyerPk: number;
  tokenHash: string;
  expiresAt: number;
  usedAt: number | null;
  createdAt: number;
};

export type AuthEvent = {
  id: number;
  buyerPk: number | null;
  eventType:
    | "signup"
    | "signin"
    | "signout"
    | "signin_failed"
    | "email_verified"
    | "password_reset"
    | "api_key_rotated"
    | "api_key_revoked"
    | "marketing_pref_changed"
    | "account_deleted";
  ip: string | null;
  userAgent: string | null;
  metadata: Record<string, unknown> | null;
  createdAt: number;
};

export interface AuthStore {
  // Buyer + credentials
  createBuyerWithCredentials(input: {
    email: string;
    passwordHash: string;
    organization: string;
    displayName: string;
    intent: Buyer["intent"];
    country: string | null;
    marketingEmailOptIn: boolean;
    pipaConsents: Record<string, string | null>;
    consentTermsVersion: string;
    apiKeyKid: string;
    apiKeyTokenHash: string;
    skipEmailVerify: boolean;
  }): Promise<{ buyer: Buyer; credentials: BuyerCredentials; apiKey: ApiKey }>;

  findCredentialsByEmail(email: string): Promise<BuyerCredentials | null>;
  findBuyer(buyerPk: number): Promise<Buyer | null>;
  findBuyerByPublicId(buyerId: string): Promise<Buyer | null>;
  findActiveApiKey(buyerPk: number): Promise<ApiKey | null>;

  markEmailVerified(buyerPk: number): Promise<void>;
  bumpSessionVersion(buyerPk: number): Promise<number>;
  updatePasswordHash(buyerPk: number, newHash: string): Promise<void>;
  updateMarketingOptIn(buyerPk: number, optIn: boolean): Promise<void>;
  softDeleteBuyer(buyerPk: number): Promise<{ deletedAt: number; hardDeleteAt: number }>;
  isEmailRecentlyDeleted(email: string, withinMs: number): Promise<boolean>;

  // OTP
  insertOtp(buyerPk: number, otpHash: string, expiresAt: number): Promise<Otp>;
  findActiveOtp(buyerPk: number): Promise<Otp | null>;
  bumpOtpAttempts(otpId: number): Promise<number>;
  invalidateOtp(otpId: number): Promise<void>;
  countRecentOtpRequests(buyerPk: number, windowMs: number): Promise<number>;

  // Password-reset token
  insertResetToken(buyerPk: number, tokenHash: string, expiresAt: number): Promise<ResetToken>;
  findActiveResetTokenByHash(tokenHash: string): Promise<ResetToken | null>;
  markResetTokenUsed(id: number): Promise<void>;
  countRecentResetRequests(buyerPk: number, windowMs: number): Promise<number>;

  // API key
  rotateApiKey(buyerPk: number, newKid: string, newTokenHash: string): Promise<ApiKey>;
  revokeApiKey(buyerPk: number): Promise<void>;
  countRecentRotations(buyerPk: number, windowMs: number): Promise<number>;

  // Audit
  insertEvent(input: {
    buyerPk: number | null;
    eventType: AuthEvent["eventType"];
    ip?: string | null;
    userAgent?: string | null;
    metadata?: Record<string, unknown> | null;
  }): Promise<AuthEvent>;
  countEventsByType(eventType: AuthEvent["eventType"]): Promise<number>;
  listEventsForBuyer(buyerPk: number): Promise<AuthEvent[]>;

  // Test helper
  reset(): void;
}

// ---------------------------------------------------------------------------
// In-memory implementation
// ---------------------------------------------------------------------------

class MemoryAuthStore implements AuthStore {
  private buyers: Map<number, Buyer> = new Map();
  private credentials: Map<number, BuyerCredentials> = new Map();
  private apiKeys: ApiKey[] = [];
  private otps: Otp[] = [];
  private resetTokens: ResetToken[] = [];
  private events: AuthEvent[] = [];
  private nextBuyerPk = 1;
  private nextOtpId = 1;
  private nextResetTokenId = 1;
  private nextEventId = 1;

  reset(): void {
    this.buyers.clear();
    this.credentials.clear();
    this.apiKeys = [];
    this.otps = [];
    this.resetTokens = [];
    this.events = [];
    this.nextBuyerPk = 1;
    this.nextOtpId = 1;
    this.nextResetTokenId = 1;
    this.nextEventId = 1;
  }

  async createBuyerWithCredentials(input: {
    email: string;
    passwordHash: string;
    organization: string;
    displayName: string;
    intent: Buyer["intent"];
    country: string | null;
    marketingEmailOptIn: boolean;
    pipaConsents: Record<string, string | null>;
    consentTermsVersion: string;
    apiKeyKid: string;
    apiKeyTokenHash: string;
    skipEmailVerify: boolean;
  }): Promise<{ buyer: Buyer; credentials: BuyerCredentials; apiKey: ApiKey }> {
    const email = input.email.toLowerCase();
    if (await this.findCredentialsByEmail(email)) {
      throw new AuthStoreError("ERR_EMAIL_TAKEN", "email already exists");
    }
    const now = Date.now();
    const buyerPk = this.nextBuyerPk++;
    const buyerId = "buy_" + randomBytes(6).toString("hex");
    const buyer: Buyer = {
      buyerPk,
      buyerId,
      displayName: input.displayName,
      organization: input.organization,
      intent: input.intent,
      country: input.country,
      contactEmail: email,
      tier: "preview",
      active: true,
      enrolledAt: now,
    };
    const credentials: BuyerCredentials = {
      buyerPk,
      email,
      passwordHash: input.passwordHash,
      emailVerifiedAt: input.skipEmailVerify ? now : null,
      marketingEmailOptIn: input.marketingEmailOptIn,
      sessionVersion: 1,
      pipaConsents: input.pipaConsents,
      consentTermsVersion: input.consentTermsVersion,
      deletedAt: null,
      createdAt: now,
      updatedAt: now,
    };
    const apiKey: ApiKey = {
      kid: input.apiKeyKid,
      buyerPk,
      tokenHash: input.apiKeyTokenHash,
      label: "default",
      tier: "preview",
      createdAt: now,
      lastUsedAt: null,
      revokedAt: null,
    };
    this.buyers.set(buyerPk, buyer);
    this.credentials.set(buyerPk, credentials);
    this.apiKeys.push(apiKey);
    return { buyer, credentials, apiKey };
  }

  async findCredentialsByEmail(email: string): Promise<BuyerCredentials | null> {
    const e = email.toLowerCase();
    for (const c of this.credentials.values()) {
      if (c.email === e && c.deletedAt === null) return c;
    }
    return null;
  }

  async findBuyer(buyerPk: number): Promise<Buyer | null> {
    return this.buyers.get(buyerPk) ?? null;
  }

  async findBuyerByPublicId(buyerId: string): Promise<Buyer | null> {
    for (const b of this.buyers.values()) if (b.buyerId === buyerId) return b;
    return null;
  }

  async findActiveApiKey(buyerPk: number): Promise<ApiKey | null> {
    // newest-first, only un-revoked
    const active = this.apiKeys
      .filter((k) => k.buyerPk === buyerPk && k.revokedAt === null)
      .sort((a, b) => b.createdAt - a.createdAt);
    return active[0] ?? null;
  }

  async markEmailVerified(buyerPk: number): Promise<void> {
    const c = this.credentials.get(buyerPk);
    if (!c) return;
    c.emailVerifiedAt = Date.now();
    c.updatedAt = Date.now();
  }

  async bumpSessionVersion(buyerPk: number): Promise<number> {
    const c = this.credentials.get(buyerPk);
    if (!c) throw new AuthStoreError("ERR_BUYER_NOT_FOUND", "buyer missing");
    c.sessionVersion += 1;
    c.updatedAt = Date.now();
    return c.sessionVersion;
  }

  async updatePasswordHash(buyerPk: number, newHash: string): Promise<void> {
    const c = this.credentials.get(buyerPk);
    if (!c) throw new AuthStoreError("ERR_BUYER_NOT_FOUND", "buyer missing");
    c.passwordHash = newHash;
    c.updatedAt = Date.now();
  }

  async updateMarketingOptIn(buyerPk: number, optIn: boolean): Promise<void> {
    const c = this.credentials.get(buyerPk);
    if (!c) return;
    c.marketingEmailOptIn = optIn;
    c.updatedAt = Date.now();
  }

  async softDeleteBuyer(
    buyerPk: number,
  ): Promise<{ deletedAt: number; hardDeleteAt: number }> {
    const c = this.credentials.get(buyerPk);
    if (!c) throw new AuthStoreError("ERR_BUYER_NOT_FOUND", "buyer missing");
    const now = Date.now();
    c.deletedAt = now;
    // mangle email so the unique constraint doesn't block the same email
    // re-signup AFTER the 30-day grace expires
    c.email = `deleted-${buyerPk}@radivault.invalid`;
    c.updatedAt = now;
    // revoke all keys
    for (const k of this.apiKeys) {
      if (k.buyerPk === buyerPk && k.revokedAt === null) k.revokedAt = now;
    }
    const hardDeleteAt = now + 30 * 24 * 60 * 60 * 1000;
    return { deletedAt: now, hardDeleteAt };
  }

  async isEmailRecentlyDeleted(email: string, withinMs: number): Promise<boolean> {
    const cutoff = Date.now() - withinMs;
    const e = email.toLowerCase();
    for (const c of this.credentials.values()) {
      if (c.deletedAt !== null && c.deletedAt > cutoff) {
        // We mangled the email on delete; recover the original via the
        // buyer's contactEmail (which we DO NOT mangle).
        const buyer = this.buyers.get(c.buyerPk);
        if (buyer && buyer.contactEmail.toLowerCase() === e) return true;
      }
    }
    return false;
  }

  async insertOtp(buyerPk: number, otpHash: string, expiresAt: number): Promise<Otp> {
    const otp: Otp = {
      id: this.nextOtpId++,
      buyerPk,
      otpHash,
      expiresAt,
      attempts: 0,
      consumedAt: null,
      createdAt: Date.now(),
    };
    this.otps.push(otp);
    return otp;
  }

  async findActiveOtp(buyerPk: number): Promise<Otp | null> {
    const now = Date.now();
    const active = this.otps
      .filter(
        (o) =>
          o.buyerPk === buyerPk &&
          o.consumedAt === null &&
          o.expiresAt > now &&
          o.attempts < 3,
      )
      .sort((a, b) => b.createdAt - a.createdAt);
    return active[0] ?? null;
  }

  async bumpOtpAttempts(otpId: number): Promise<number> {
    const o = this.otps.find((x) => x.id === otpId);
    if (!o) return 0;
    o.attempts += 1;
    return o.attempts;
  }

  async invalidateOtp(otpId: number): Promise<void> {
    const o = this.otps.find((x) => x.id === otpId);
    if (o) o.consumedAt = Date.now();
  }

  async countRecentOtpRequests(buyerPk: number, windowMs: number): Promise<number> {
    const cutoff = Date.now() - windowMs;
    return this.otps.filter((o) => o.buyerPk === buyerPk && o.createdAt > cutoff)
      .length;
  }

  async insertResetToken(
    buyerPk: number,
    tokenHash: string,
    expiresAt: number,
  ): Promise<ResetToken> {
    const t: ResetToken = {
      id: this.nextResetTokenId++,
      buyerPk,
      tokenHash,
      expiresAt,
      usedAt: null,
      createdAt: Date.now(),
    };
    this.resetTokens.push(t);
    return t;
  }

  async findActiveResetTokenByHash(tokenHash: string): Promise<ResetToken | null> {
    const now = Date.now();
    return (
      this.resetTokens.find(
        (t) => t.tokenHash === tokenHash && t.usedAt === null && t.expiresAt > now,
      ) ?? null
    );
  }

  async markResetTokenUsed(id: number): Promise<void> {
    const t = this.resetTokens.find((x) => x.id === id);
    if (t) t.usedAt = Date.now();
  }

  async countRecentResetRequests(buyerPk: number, windowMs: number): Promise<number> {
    const cutoff = Date.now() - windowMs;
    return this.resetTokens.filter(
      (t) => t.buyerPk === buyerPk && t.createdAt > cutoff,
    ).length;
  }

  async rotateApiKey(
    buyerPk: number,
    newKid: string,
    newTokenHash: string,
  ): Promise<ApiKey> {
    const now = Date.now();
    for (const k of this.apiKeys) {
      if (k.buyerPk === buyerPk && k.revokedAt === null) k.revokedAt = now;
    }
    const fresh: ApiKey = {
      kid: newKid,
      buyerPk,
      tokenHash: newTokenHash,
      label: "default",
      tier: "preview",
      createdAt: now,
      lastUsedAt: null,
      revokedAt: null,
    };
    this.apiKeys.push(fresh);
    return fresh;
  }

  async revokeApiKey(buyerPk: number): Promise<void> {
    const now = Date.now();
    for (const k of this.apiKeys) {
      if (k.buyerPk === buyerPk && k.revokedAt === null) k.revokedAt = now;
    }
  }

  async countRecentRotations(buyerPk: number, windowMs: number): Promise<number> {
    const cutoff = Date.now() - windowMs;
    // count revocations in window (one rotation = one revoke)
    return this.apiKeys.filter(
      (k) => k.buyerPk === buyerPk && k.revokedAt !== null && k.revokedAt > cutoff,
    ).length;
  }

  async insertEvent(input: {
    buyerPk: number | null;
    eventType: AuthEvent["eventType"];
    ip?: string | null;
    userAgent?: string | null;
    metadata?: Record<string, unknown> | null;
  }): Promise<AuthEvent> {
    const ev: AuthEvent = {
      id: this.nextEventId++,
      buyerPk: input.buyerPk,
      eventType: input.eventType,
      ip: input.ip ?? null,
      userAgent: input.userAgent ?? null,
      metadata: input.metadata ?? null,
      createdAt: Date.now(),
    };
    this.events.push(ev);
    return ev;
  }

  async countEventsByType(eventType: AuthEvent["eventType"]): Promise<number> {
    return this.events.filter((e) => e.eventType === eventType).length;
  }

  async listEventsForBuyer(buyerPk: number): Promise<AuthEvent[]> {
    return this.events
      .filter((e) => e.buyerPk === buyerPk)
      .sort((a, b) => b.createdAt - a.createdAt);
  }
}

export class AuthStoreError extends Error {
  constructor(public code: string, message: string) {
    super(message);
    this.name = "AuthStoreError";
  }
}

// Singleton — pinned on globalThis so Next.js dev-mode module re-imports
// (Fast Refresh + per-request route compilation) don't blow away the
// in-memory state between signup and signin within the same test run.
//
// In production (``next start``) and vitest (single Node process) this
// behaves identically to a module-local ``let`` — globalThis is the same
// object across all imports.
const SINGLETON_KEY = "__radivault_auth_store_v1__";

declare global {
  // eslint-disable-next-line no-var
  var __radivault_auth_store_v1__: AuthStore | undefined;
}

export function getAuthStore(): AuthStore {
  const g = globalThis as typeof globalThis & {
    [SINGLETON_KEY]?: AuthStore;
  };
  if (!g[SINGLETON_KEY]) {
    g[SINGLETON_KEY] = new MemoryAuthStore();
  }
  return g[SINGLETON_KEY] as AuthStore;
}
