/**
 * POST /api/auth/signup — dev-spec-buyer-auth FR-AUTH-1.
 *
 * Flow:
 *   1. zod validate (incl. PIPA 3-of-3 if locale=ko)
 *   2. ERR_EMAIL_TAKEN / ERR_EMAIL_RECENTLY_DELETED checks
 *   3. argon2.hash(password)  ~50ms
 *   4. mintApiKey() → kid + tokenHash + plaintext (returned ONCE)
 *   5. store.createBuyerWithCredentials() — single transaction in store
 *   6. iron-session set
 *   7. (skip-flag false) generate + insert OTP, log to stdout in dev/demo
 *   8. INSERT auth_session_event(signup)
 *   9. 201 + Set-Cookie + apiKeyRevealOnce body
 *
 * Rate limit: 1/min/IP.
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { signupSchema } from "@/lib/auth/schemas";
import { hashPassword } from "@/lib/auth/argon2";
import { generateOtp, hashOtp } from "@/lib/auth/otp";
import { mintApiKey } from "@/lib/auth/api-key";
import { getAuthStore, AuthStoreError } from "@/lib/auth/store";
import { signupRateLimiter } from "@/lib/rate-limit";
import { authError, newRequestId, resolveClientIp, resolveUserAgent } from "@/lib/auth/responses";
import { getBuyerSession } from "@/lib/session";
import { env } from "@/lib/env";

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;
const OTP_TTL_MS = 10 * 60 * 1000;

export async function POST(req: Request) {
  const requestId = newRequestId();
  const ip = resolveClientIp(req.headers);
  const ua = resolveUserAgent(req.headers);

  // Rate limit early — pre-zod so a flood can't burn CPU on validation.
  const rl = signupRateLimiter.check(`ip:${ip}`);
  if (!rl.ok) {
    return authError(
      "ERR_RATE_LIMITED",
      `Too many signup attempts. Try again in ${rl.retryAfterSeconds}s.`,
      429,
      undefined,
      requestId,
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return authError("ERR_VALIDATION", "Invalid JSON body.", 400, undefined, requestId);
  }

  let parsed;
  try {
    parsed = signupSchema.parse(body);
  } catch (e) {
    if (e instanceof ZodError) {
      const first = e.errors[0];
      const field = first.path.join(".");
      const code = String(first.message).startsWith("ERR_VALIDATION")
        ? String(first.message).split(":")[0]
        : "ERR_VALIDATION";
      return authError(
        code,
        first.message ?? "Validation failed.",
        400,
        field || undefined,
        requestId,
      );
    }
    return authError("ERR_VALIDATION", "Validation failed.", 400, undefined, requestId);
  }

  // KR locale must include PIPA consent block; EN locale must NOT.
  if (parsed.locale === "ko") {
    if (!parsed.pipaConsents) {
      return authError(
        "ERR_VALIDATION",
        "PIPA consents required on Korean signup.",
        400,
        "pipaConsents",
        requestId,
      );
    }
  }

  const store = getAuthStore();

  // ERR_EMAIL_RECENTLY_DELETED — within 30d grace.
  if (await store.isEmailRecentlyDeleted(parsed.email, THIRTY_DAYS_MS)) {
    return authError(
      "ERR_EMAIL_RECENTLY_DELETED",
      "This email was recently deleted. Please wait 30 days or contact sales.",
      409,
      "email",
      requestId,
    );
  }

  // ERR_EMAIL_TAKEN — duplicate non-deleted credential row.
  if (await store.findCredentialsByEmail(parsed.email)) {
    return authError(
      "ERR_EMAIL_TAKEN",
      "An account already exists for this email.",
      409,
      "email",
      requestId,
    );
  }

  // Argon2 hash + API key mint happen in parallel — both are CPU-bound +
  // independent.
  const passwordHash = await hashPassword(parsed.password);
  const minted = mintApiKey();

  const consents: Record<string, string | null> = parsed.pipaConsents
    ? {
        collectUse: parsed.pipaConsents.collectUse ? new Date().toISOString() : null,
        thirdParty: parsed.pipaConsents.thirdParty ? new Date().toISOString() : null,
        crossBorder: parsed.pipaConsents.crossBorder
          ? new Date().toISOString()
          : null,
        marketing: parsed.pipaConsents.marketing ? new Date().toISOString() : null,
      }
    : {
        tosPrivacy: parsed.tosPrivacyConsent ? new Date().toISOString() : null,
        marketing: parsed.marketingEmailOptIn ? new Date().toISOString() : null,
      };

  let created;
  try {
    created = await store.createBuyerWithCredentials({
      email: parsed.email,
      passwordHash,
      organization: parsed.organization,
      displayName: parsed.displayName ?? parsed.organization,
      intent: parsed.intent,
      country: parsed.country ?? null,
      marketingEmailOptIn: parsed.marketingEmailOptIn,
      pipaConsents: consents,
      consentTermsVersion: "tos-v1.0;privacy-v1.0",
      apiKeyKid: minted.kid,
      apiKeyTokenHash: minted.tokenHash,
      skipEmailVerify: env.buyerAuthSkipEmailVerify,
    });
  } catch (err) {
    if (err instanceof AuthStoreError && err.code === "ERR_EMAIL_TAKEN") {
      return authError(
        "ERR_EMAIL_TAKEN",
        "An account already exists for this email.",
        409,
        "email",
        requestId,
      );
    }
    return authError(
      "ERR_INTERNAL",
      "Could not create account. Please retry.",
      500,
      undefined,
      requestId,
    );
  }

  // Issue OTP unless skip-flag.
  if (!env.buyerAuthSkipEmailVerify) {
    const code = generateOtp();
    const hashedOtp = hashOtp(code, created.buyer.buyerPk);
    await store.insertOtp(
      created.buyer.buyerPk,
      hashedOtp,
      Date.now() + OTP_TTL_MS,
    );
    // Dev/demo: stdout JSON marker so the operator can copy the code.
    // dev-spec FR-AUTH-2: production replaces this with AWS SES.
    // eslint-disable-next-line no-console
    console.log(
      JSON.stringify({
        marker: "OTP_DEV",
        buyerId: created.buyer.buyerId,
        email: created.buyer.contactEmail,
        otp: code,
        expiresInSec: OTP_TTL_MS / 1000,
      }),
    );
  }

  await store.insertEvent({
    buyerPk: created.buyer.buyerPk,
    eventType: "signup",
    ip,
    userAgent: ua,
    metadata: { kid: minted.kid, locale: parsed.locale },
  });

  // iron-session — v0.2 payload. Plaintext API key NEVER goes in the
  // cookie; it lives only in this response body.
  const session = await getBuyerSession();
  session.buyerPk = created.buyer.buyerPk;
  session.buyerId = created.buyer.buyerId;
  session.email = created.buyer.contactEmail;
  session.emailVerified = created.credentials.emailVerifiedAt !== null;
  session.sessionVersion = created.credentials.sessionVersion;
  session.locale = parsed.locale;
  session.tier = created.buyer.tier;
  session.signedInAt = Date.now();
  // legacy field intentionally NOT set — new signups don't paste keys
  delete session.apiKey;
  await session.save();

  return NextResponse.json(
    {
      buyerId: created.buyer.buyerId,
      email: created.buyer.contactEmail,
      emailVerified: created.credentials.emailVerifiedAt !== null,
      apiKeyRevealOnce: minted.plaintext,
      apiKeyKid: minted.kid,
      next: "/search",
      request_id: requestId,
    },
    { status: 201 },
  );
}
