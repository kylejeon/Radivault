/**
 * POST /api/auth/verify-email — dev-spec-buyer-auth FR-AUTH-2.
 *
 * Body: { email, otp }. Looks up the active OTP row for the email's buyer,
 * verifies hash, and stamps emailVerifiedAt. 3-attempt lockout per row.
 *
 * When BUYER_AUTH_SKIP_EMAIL_VERIFY=true the row was never inserted; we
 * mark verified directly and return 200 (FR-AUTH-2).
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { verifyEmailSchema } from "@/lib/auth/schemas";
import { hashOtp, compareOtpHash } from "@/lib/auth/otp";
import { getAuthStore } from "@/lib/auth/store";
import { authError, newRequestId, resolveClientIp, resolveUserAgent } from "@/lib/auth/responses";
import { getBuyerSession } from "@/lib/session";
import { env } from "@/lib/env";

export async function POST(req: Request) {
  const requestId = newRequestId();
  const ip = resolveClientIp(req.headers);
  const ua = resolveUserAgent(req.headers);

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return authError("ERR_VALIDATION", "Invalid JSON body.", 400, undefined, requestId);
  }

  let parsed;
  try {
    parsed = verifyEmailSchema.parse(body);
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

  const store = getAuthStore();
  const credentials = await store.findCredentialsByEmail(parsed.email);
  if (!credentials) {
    return authError(
      "ERR_BUYER_NOT_FOUND",
      "Account not found.",
      404,
      "email",
      requestId,
    );
  }

  // Skip-flag: signup already marked verified. No-op success.
  if (env.buyerAuthSkipEmailVerify) {
    if (credentials.emailVerifiedAt === null) {
      await store.markEmailVerified(credentials.buyerPk);
    }
    const session = await getBuyerSession();
    if (session.buyerPk === credentials.buyerPk) {
      session.emailVerified = true;
      await session.save();
    }
    return NextResponse.json(
      { verifiedAt: new Date().toISOString(), request_id: requestId },
      { status: 200 },
    );
  }

  const otp = await store.findActiveOtp(credentials.buyerPk);
  if (!otp) {
    return authError(
      "ERR_OTP_EXPIRED",
      "Verification code expired. Request a new one.",
      400,
      undefined,
      requestId,
    );
  }

  const attempted = hashOtp(parsed.otp, credentials.buyerPk);
  if (!compareOtpHash(attempted, otp.otpHash)) {
    const attempts = await store.bumpOtpAttempts(otp.id);
    if (attempts >= 3) {
      await store.invalidateOtp(otp.id);
      return authError(
        "ERR_OTP_LOCKED",
        "Too many attempts. Request a new code.",
        423,
        undefined,
        requestId,
      );
    }
    return authError(
      "ERR_OTP_INVALID",
      `Verification code is incorrect. ${3 - attempts} attempt(s) remaining.`,
      400,
      "otp",
      requestId,
    );
  }

  // Success.
  await store.invalidateOtp(otp.id);
  await store.markEmailVerified(credentials.buyerPk);
  await store.insertEvent({
    buyerPk: credentials.buyerPk,
    eventType: "email_verified",
    ip,
    userAgent: ua,
  });

  // Refresh session if the verifying user is the active session.
  const session = await getBuyerSession();
  if (session.buyerPk === credentials.buyerPk) {
    session.emailVerified = true;
    await session.save();
  }

  return NextResponse.json(
    { verifiedAt: new Date().toISOString(), request_id: requestId },
    { status: 200 },
  );
}
