/**
 * POST /api/auth/signin — dev-spec-buyer-auth FR-AUTH-4.
 *
 * Timing-safe (AC-AUTH-4.2): nonexistent-email path runs argon2.verify
 * against TIMING_SAFE_DUMMY_HASH so the response shape and elapsed time
 * match the wrong-password path.
 *
 * Rate limit: 5/min/IP + 10/hour/account → 423 ERR_ACCOUNT_LOCKED.
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { signinSchema } from "@/lib/auth/schemas";
import {
  verifyPassword,
  TIMING_SAFE_DUMMY_HASH,
} from "@/lib/auth/argon2";
import { getAuthStore } from "@/lib/auth/store";
import {
  signinIpRateLimiter,
  signinAccountRateLimiter,
} from "@/lib/rate-limit";
import {
  authError,
  newRequestId,
  resolveClientIp,
  resolveUserAgent,
} from "@/lib/auth/responses";
import { getBuyerSession } from "@/lib/session";

export async function POST(req: Request) {
  const requestId = newRequestId();
  const ip = resolveClientIp(req.headers);
  const ua = resolveUserAgent(req.headers);

  const ipRl = signinIpRateLimiter.check(`ip:${ip}`);
  if (!ipRl.ok) {
    return authError(
      "ERR_RATE_LIMITED",
      `Too many sign-in attempts. Try again in ${ipRl.retryAfterSeconds}s.`,
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
    parsed = signinSchema.parse(body);
  } catch (e) {
    if (e instanceof ZodError) {
      const first = e.errors[0];
      return authError(
        "ERR_VALIDATION",
        first.message,
        400,
        first.path.join(".") || undefined,
        requestId,
      );
    }
    return authError("ERR_VALIDATION", "Validation failed.", 400, undefined, requestId);
  }

  const accountRl = signinAccountRateLimiter.check(`acc:${parsed.email}`);
  if (!accountRl.ok) {
    return authError(
      "ERR_ACCOUNT_LOCKED",
      "Account locked for 15 minutes due to repeated failures.",
      423,
      undefined,
      requestId,
    );
  }

  const store = getAuthStore();
  const credentials = await store.findCredentialsByEmail(parsed.email);

  // Timing-safe path: always run a verify even when no row exists.
  const hashToVerify = credentials?.passwordHash ?? TIMING_SAFE_DUMMY_HASH;
  const verified = await verifyPassword(hashToVerify, parsed.password);

  if (!credentials || !verified) {
    if (credentials) {
      await store.insertEvent({
        buyerPk: credentials.buyerPk,
        eventType: "signin_failed",
        ip,
        userAgent: ua,
      });
    }
    return authError(
      "ERR_AUTH_INVALID",
      "Email or password is incorrect.",
      401,
      undefined,
      requestId,
    );
  }

  const buyer = await store.findBuyer(credentials.buyerPk);
  if (!buyer) {
    return authError(
      "ERR_INTERNAL",
      "Account state inconsistent — contact support.",
      500,
      undefined,
      requestId,
    );
  }

  await store.insertEvent({
    buyerPk: credentials.buyerPk,
    eventType: "signin",
    ip,
    userAgent: ua,
  });

  const session = await getBuyerSession();
  session.buyerPk = credentials.buyerPk;
  session.buyerId = buyer.buyerId;
  session.email = credentials.email;
  session.emailVerified = credentials.emailVerifiedAt !== null;
  session.sessionVersion = credentials.sessionVersion;
  session.locale = "en";
  session.tier = buyer.tier;
  session.signedInAt = Date.now();
  session.org = buyer.organization;
  delete session.apiKey;
  await session.save();

  return NextResponse.json(
    {
      buyerId: buyer.buyerId,
      email: credentials.email,
      emailVerified: credentials.emailVerifiedAt !== null,
      next: "/search",
      request_id: requestId,
    },
    { status: 200 },
  );
}
