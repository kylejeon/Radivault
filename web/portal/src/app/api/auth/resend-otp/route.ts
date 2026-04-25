/**
 * POST /api/auth/resend-otp — dev-spec-buyer-auth FR-AUTH-2.
 *
 * Always 200 (account-existence-leakage prevention, B2B standard). When
 * skip-flag is on, the response is identical but no OTP row is inserted.
 *
 * Rate limit: 3 / 15min / account.
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { resendOtpSchema } from "@/lib/auth/schemas";
import { generateOtp, hashOtp } from "@/lib/auth/otp";
import { getAuthStore } from "@/lib/auth/store";
import { otpResendRateLimiter } from "@/lib/rate-limit";
import { authError, newRequestId } from "@/lib/auth/responses";
import { env } from "@/lib/env";

const OTP_TTL_MS = 10 * 60 * 1000;

export async function POST(req: Request) {
  const requestId = newRequestId();

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return authError("ERR_VALIDATION", "Invalid JSON body.", 400, undefined, requestId);
  }

  let parsed;
  try {
    parsed = resendOtpSchema.parse(body);
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

  const rl = otpResendRateLimiter.check(`acc:${parsed.email}`);
  if (!rl.ok) {
    return authError(
      "ERR_RATE_LIMITED",
      `Limit reached. Try again in ${rl.retryAfterSeconds}s.`,
      429,
      undefined,
      requestId,
    );
  }

  // Always 200 — even if email doesn't exist.
  if (env.buyerAuthSkipEmailVerify) {
    return NextResponse.json({ sent: true, request_id: requestId }, { status: 200 });
  }

  const store = getAuthStore();
  const credentials = await store.findCredentialsByEmail(parsed.email);
  if (credentials) {
    const code = generateOtp();
    await store.insertOtp(
      credentials.buyerPk,
      hashOtp(code, credentials.buyerPk),
      Date.now() + OTP_TTL_MS,
    );
    // eslint-disable-next-line no-console
    console.log(
      JSON.stringify({
        marker: "OTP_DEV",
        buyerId: credentials.buyerPk,
        email: credentials.email,
        otp: code,
        expiresInSec: OTP_TTL_MS / 1000,
      }),
    );
  }

  return NextResponse.json({ sent: true, request_id: requestId }, { status: 200 });
}
