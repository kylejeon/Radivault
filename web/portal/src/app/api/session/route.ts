import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";

/**
 * POST /api/session — buyer sign-in (FR-A-4).
 *
 * 1. parse { apiKey }
 * 2. validate prefix (rv_live_ or rv_test_)
 * 3. call metadata-index /v1/search/facets as a cheap "ping" using the key
 * 4. on 200, write the encrypted key + metadata into rv_session cookie
 */
export async function POST(req: Request) {
  let apiKey: string;
  try {
    const body = (await req.json()) as { apiKey?: string };
    apiKey = (body.apiKey ?? "").trim();
  } catch {
    return NextResponse.json(
      { error: "ERR_AUTH_FORMAT", detail: "Invalid JSON body" },
      { status: 400 },
    );
  }
  if (!apiKey.startsWith("rv_live_") && !apiKey.startsWith("rv_test_")) {
    return NextResponse.json(
      { error: "ERR_AUTH_FORMAT", detail: "API key must start with rv_live_ or rv_test_" },
      { status: 400 },
    );
  }
  const probe = await upstreamFetch(bases.search, "/v1/search/facets", {
    bearer: apiKey,
  });
  if (!probe.ok) {
    const status = probe.status === 401 ? 401 : probe.status === 403 ? 403 : 502;
    return NextResponse.json(
      { error: probe.code, detail: probe.detail, request_id: probe.requestId },
      { status },
    );
  }
  const session = await getBuyerSession();
  session.apiKey = apiKey;
  session.signedInAt = Date.now();
  await session.save();
  return NextResponse.json({ ok: true });
}
