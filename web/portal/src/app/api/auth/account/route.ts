/**
 * DELETE /api/auth/account — dev-spec-buyer-auth FR-AUTH-11.
 *
 * Body: { emailConfirmation }. Soft delete + revoke all keys + 30-day grace
 * (hard delete cron is v0.1.5). Session destroyed unconditionally.
 */

import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { deleteAccountSchema } from "@/lib/auth/schemas";
import { getAuthStore } from "@/lib/auth/store";
import { getBuyerSession } from "@/lib/session";
import { authError, newRequestId, resolveClientIp, resolveUserAgent } from "@/lib/auth/responses";

export async function DELETE(req: Request) {
  const requestId = newRequestId();
  const ip = resolveClientIp(req.headers);
  const ua = resolveUserAgent(req.headers);

  const session = await getBuyerSession();
  if (!session.buyerPk || !session.email) {
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
    parsed = deleteAccountSchema.parse(body);
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

  if (parsed.emailConfirmation.toLowerCase() !== session.email.toLowerCase()) {
    return authError(
      "ERR_VALIDATION",
      "Email confirmation does not match your account.",
      400,
      "emailConfirmation",
      requestId,
    );
  }

  const store = getAuthStore();
  const { deletedAt, hardDeleteAt } = await store.softDeleteBuyer(session.buyerPk);
  await store.insertEvent({
    buyerPk: session.buyerPk,
    eventType: "account_deleted",
    ip,
    userAgent: ua,
    metadata: { hardDeleteAt },
  });

  session.destroy();

  return NextResponse.json(
    {
      deletedAt: new Date(deletedAt).toISOString(),
      hardDeleteAt: new Date(hardDeleteAt).toISOString(),
      redirect: "/",
      request_id: requestId,
    },
    { status: 200 },
  );
}
