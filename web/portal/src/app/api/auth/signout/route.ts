/**
 * POST /api/auth/signout — dev-spec-buyer-auth FR-AUTH-5.
 *
 * Destroys the iron-session cookie + writes signout audit row. Always 200,
 * even when no session exists (idempotent — UX of double-clicking signout
 * shouldn't show an error).
 */

import { NextResponse } from "next/server";

import { getBuyerSession } from "@/lib/session";
import { getAuthStore } from "@/lib/auth/store";
import { newRequestId, resolveClientIp, resolveUserAgent } from "@/lib/auth/responses";

export async function POST(req: Request) {
  const requestId = newRequestId();
  const session = await getBuyerSession();
  const buyerPk = session.buyerPk ?? null;
  const ip = resolveClientIp(req.headers);
  const ua = resolveUserAgent(req.headers);

  if (buyerPk !== null) {
    await getAuthStore().insertEvent({
      buyerPk,
      eventType: "signout",
      ip,
      userAgent: ua,
    });
  }

  session.destroy();
  return NextResponse.json({ redirect: "/", request_id: requestId }, { status: 200 });
}
