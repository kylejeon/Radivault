import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";

/**
 * BFF: GET /api/search/studies/[uid]
 *
 * dev-spec-portal-redesign FR-BP-8 / FR-BP-17.
 * Pure passthrough to search service `GET /v1/search/studies/{uid}` —
 * shape mirrors `SearchStudyDetail` (StudyItem fields + series[]).
 */
export async function GET(
  _req: Request,
  context: { params: Promise<{ uid: string }> },
) {
  const session = await getBuyerSession();
  if (!session.buyerPk && !session.apiKey) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "No session" },
      { status: 401 },
    );
  }
  const resolved = bearerForBuyer(session);
  if (!resolved.ok) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: resolved.reason },
      { status: 401 },
    );
  }
  const { uid } = await context.params;
  const res = await upstreamFetch(
    bases.search,
    `/v1/search/studies/${encodeURIComponent(uid)}`,
    {
      bearer: resolved.bearer,
      headers: actingBuyerHeaders(session, resolved.mode),
    },
  );
  if (!res.ok) {
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  return NextResponse.json(res.data);
}
