/**
 * GET /api/account/api-key — dev-spec-buyer-auth FR-AUTH-8.
 *   Returns kid + masked + tier + createdAt + lastUsedAt. NEVER plaintext.
 *
 * POST /api/account/api-key { action: 'regenerate' | 'revoke' }
 *   - regenerate: revoke existing + mint new + ONE-TIME plaintext in body.
 *   - revoke    : revoke only. UI surfaces the empty state.
 *
 * Rate limit: 3 / hour / buyer (rotate only).
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { apiKeyActionSchema } from "@/lib/auth/schemas";
import { mintApiKey, maskKid } from "@/lib/auth/api-key";
import { getAuthStore } from "@/lib/auth/store";
import { apiKeyRotateRateLimiter } from "@/lib/rate-limit";
import { authError, newRequestId, resolveClientIp, resolveUserAgent } from "@/lib/auth/responses";
import { getBuyerSession } from "@/lib/session";

export async function GET() {
  const requestId = newRequestId();
  const session = await getBuyerSession();
  if (!session.buyerPk) {
    return authError("ERR_UNAUTHORIZED", "Sign in required.", 401, undefined, requestId);
  }

  const store = getAuthStore();
  const key = await store.findActiveApiKey(session.buyerPk);
  if (!key) {
    return authError(
      "ERR_NO_ACTIVE_KEY",
      "No active API key. Generate one from /account.",
      404,
      undefined,
      requestId,
    );
  }

  return NextResponse.json(
    {
      kid: key.kid,
      masked: maskKid(key.kid),
      label: key.label,
      tier: key.tier,
      createdAt: new Date(key.createdAt).toISOString(),
      lastUsedAt: key.lastUsedAt ? new Date(key.lastUsedAt).toISOString() : null,
      request_id: requestId,
    },
    { status: 200 },
  );
}

export async function POST(req: Request) {
  const requestId = newRequestId();
  const ip = resolveClientIp(req.headers);
  const ua = resolveUserAgent(req.headers);

  const session = await getBuyerSession();
  if (!session.buyerPk) {
    return authError("ERR_UNAUTHORIZED", "Sign in required.", 401, undefined, requestId);
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return authError("ERR_VALIDATION", "Invalid JSON body.", 400, undefined, requestId);
  }

  let parsed;
  try {
    parsed = apiKeyActionSchema.parse(body);
  } catch (e) {
    if (e instanceof ZodError) {
      const first = e.errors[0];
      return authError(
        "ERR_VALIDATION",
        first.message,
        400,
        first.path.join("."),
        requestId,
      );
    }
    return authError("ERR_VALIDATION", "Validation failed.", 400, undefined, requestId);
  }

  const rl = apiKeyRotateRateLimiter.check(`buyer:${session.buyerPk}`);
  if (!rl.ok) {
    return authError(
      "ERR_RATE_LIMITED",
      `Try again in ${rl.retryAfterSeconds}s.`,
      429,
      undefined,
      requestId,
    );
  }

  const store = getAuthStore();
  if (parsed.action === "revoke") {
    await store.revokeApiKey(session.buyerPk);
    await store.insertEvent({
      buyerPk: session.buyerPk,
      eventType: "api_key_revoked",
      ip,
      userAgent: ua,
    });
    const key = await store.findActiveApiKey(session.buyerPk); // null
    return NextResponse.json(
      {
        kid: key?.kid ?? null,
        status: "revoked",
        request_id: requestId,
      },
      { status: 200 },
    );
  }

  // regenerate
  const minted = mintApiKey();
  const fresh = await store.rotateApiKey(session.buyerPk, minted.kid, minted.tokenHash);
  await store.insertEvent({
    buyerPk: session.buyerPk,
    eventType: "api_key_rotated",
    ip,
    userAgent: ua,
    metadata: { newKid: fresh.kid },
  });
  return NextResponse.json(
    {
      kid: fresh.kid,
      masked: maskKid(fresh.kid),
      plaintext: minted.plaintext, // ONE-TIME
      tier: fresh.tier,
      request_id: requestId,
    },
    { status: 200 },
  );
}
