/**
 * POST /api/auth/password-reset/confirm — dev-spec-buyer-auth FR-AUTH-6.
 *
 * Body: { token, newPassword }. SHA-256 lookup → password rehash →
 * sessionVersion bump (invalidates any active iron-session) → mark used.
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { passwordResetConfirmSchema } from "@/lib/auth/schemas";
import { hashPassword } from "@/lib/auth/argon2";
import { hashResetToken } from "@/lib/auth/otp";
import { getAuthStore } from "@/lib/auth/store";
import { authError, newRequestId, resolveClientIp, resolveUserAgent } from "@/lib/auth/responses";

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
    parsed = passwordResetConfirmSchema.parse(body);
  } catch (e) {
    if (e instanceof ZodError) {
      const first = e.errors[0];
      return authError("ERR_VALIDATION", first.message, 400, first.path.join("."), requestId);
    }
    return authError("ERR_VALIDATION", "Validation failed.", 400, undefined, requestId);
  }

  const store = getAuthStore();
  const tokenRow = await store.findActiveResetTokenByHash(hashResetToken(parsed.token));
  if (!tokenRow) {
    return authError(
      "ERR_TOKEN_INVALID",
      "This reset link is invalid or expired. Request a new one.",
      400,
      undefined,
      requestId,
    );
  }

  const newHash = await hashPassword(parsed.newPassword);
  await store.updatePasswordHash(tokenRow.buyerPk, newHash);
  await store.markResetTokenUsed(tokenRow.id);
  await store.bumpSessionVersion(tokenRow.buyerPk); // kills all active sessions
  await store.insertEvent({
    buyerPk: tokenRow.buyerPk,
    eventType: "password_reset",
    ip,
    userAgent: ua,
  });

  return NextResponse.json(
    { reset: true, redirect: "/signin", request_id: requestId },
    { status: 200 },
  );
}
