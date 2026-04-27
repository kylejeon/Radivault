import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";

/**
 * GET /api/search/autocomplete?q=&limit=
 *
 * Proxies to search service /v1/search/autocomplete (text-search-description
 * FR-TS-8). Mirrors the established pattern of /api/search/kcd-autocomplete:
 * resolve buyer session → bearer + acting headers → upstream → passthrough.
 *
 * Hard-caps `limit` at 12 (design-spec §7.1) so a malicious buyer cannot
 * widen the dropdown beyond what the autocomplete endpoint protects against.
 * `q` shorter than 2 chars is treated as an empty result client-side, but we
 * still forward 1-char queries for parity with the upstream contract.
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
  const limitRaw = url.searchParams.get("limit") ?? "10";
  const limitParsed = Number.parseInt(limitRaw, 10);
  const limitClamped = Number.isFinite(limitParsed)
    ? Math.max(1, Math.min(12, limitParsed))
    : 10;
  if (!q.trim()) {
    return NextResponse.json(
      { error: "ERR_INVALID_QUERY", detail: "q must not be empty" },
      { status: 400 },
    );
  }
  const qs = new URLSearchParams({
    q,
    limit: String(limitClamped),
  }).toString();
  const res = await upstreamFetch(
    bases.search,
    `/v1/search/autocomplete?${qs}`,
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
