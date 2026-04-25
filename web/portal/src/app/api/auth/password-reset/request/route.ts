/**
 * POST /api/auth/password-reset/request — dev-spec-buyer-auth FR-AUTH-6.
 *
 * Always 200 (no email-existence leakage). Rate limit 3/hour/IP.
 * Token: 32-byte base64url, 60min TTL. URL printed to stdout in dev/demo.
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { passwordResetRequestSchema } from "@/lib/auth/schemas";
import { generateResetToken, hashResetToken } from "@/lib/auth/otp";
import { getAuthStore } from "@/lib/auth/store";
import { passwordResetIpRateLimiter } from "@/lib/rate-limit";
import { authError, newRequestId, resolveClientIp } from "@/lib/auth/responses";
import { env } from "@/lib/env";

const RESET_TTL_MS = 60 * 60 * 1000;

export async function POST(req: Request) {
  const requestId = newRequestId();
  const ip = resolveClientIp(req.headers);

  if (env.buyerAuthPwdResetDisabled) {
    // Demo mode: stub. Still 200 so UI flow doesn't change.
    return NextResponse.json(
      { sent: true, request_id: requestId, demoStub: true },
      { status: 200 },
    );
  }

  const rl = passwordResetIpRateLimiter.check(`ip:${ip}`);
  if (!rl.ok) {
    return authError(
      "ERR_RATE_LIMITED",
      `Try again in ${rl.retryAfterSeconds}s.`,
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
    parsed = passwordResetRequestSchema.parse(body);
  } catch (e) {
    if (e instanceof ZodError) {
      const first = e.errors[0];
      return authError("ERR_VALIDATION", first.message, 400, first.path.join("."), requestId);
    }
    return authError("ERR_VALIDATION", "Validation failed.", 400, undefined, requestId);
  }

  const store = getAuthStore();
  const credentials = await store.findCredentialsByEmail(parsed.email);
  if (credentials) {
    const token = generateResetToken();
    await store.insertResetToken(
      credentials.buyerPk,
      hashResetToken(token),
      Date.now() + RESET_TTL_MS,
    );
    // eslint-disable-next-line no-console
    console.log(
      JSON.stringify({
        marker: "PWD_RESET_DEV",
        buyerId: credentials.buyerPk,
        email: credentials.email,
        url: `/password-reset/confirm?token=${token}`,
        expiresInSec: RESET_TTL_MS / 1000,
      }),
    );
  }

  return NextResponse.json({ sent: true, request_id: requestId }, { status: 200 });
}
