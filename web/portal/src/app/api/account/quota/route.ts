/**
 * BFF: GET /api/account/quota
 *
 * dev-spec-buyer-browse-preview FR-DOWNLOAD-1 (Q-6 / K-3): expose the
 * Redis quota counter so the /account page (and any other UI surface)
 * can show today's sample-download usage without round-tripping through
 * a sample-download POST.
 */

import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";

type QuotaResponse = {
  daily_used: number;
  daily_limit: number;
  resets_at: string | null;
  available: boolean;
};

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await getBuyerSession();
  if (!session.buyerPk && !session.apiKey) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "No session" },
      { status: 401 },
    );
  }
  if (!session.apiKey) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "Session has no API key" },
      { status: 401 },
    );
  }

  const res = await upstreamFetch<QuotaResponse>(
    bases.search,
    "/v1/account/quota",
    { bearer: session.apiKey },
  );
  if (!res.ok) {
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  return NextResponse.json(res.data, { status: 200 });
}
