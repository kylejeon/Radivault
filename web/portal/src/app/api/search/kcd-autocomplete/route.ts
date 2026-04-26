import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";

/**
 * GET /api/search/kcd-autocomplete?q=&limit=
 * Proxies to search service /v1/search/kcd-autocomplete (FR-V3-API-4 / FR-V3-BFF-3).
 *
 * Buyer session preserved through `bearerForBuyer` + `actingBuyerHeaders` —
 * same pattern as /api/search/studies + /facets.
 */
export async function GET(req: Request) {
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
  const url = new URL(req.url);
  const q = url.searchParams.get("q") ?? "";
  const limit = url.searchParams.get("limit") ?? "12";
  if (!q.trim()) {
    return NextResponse.json(
      { error: "ERR_INVALID_QUERY", detail: "q must not be empty" },
      { status: 400 },
    );
  }
  const qs = new URLSearchParams({ q, limit }).toString();
  const res = await upstreamFetch(
    bases.search,
    `/v1/search/kcd-autocomplete?${qs}`,
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
