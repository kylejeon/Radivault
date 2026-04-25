/**
 * BFF: POST /api/studies/[uid]/sample-download
 *
 * dev-spec-buyer-browse-preview FR-API-2 / FR-DOWNLOAD-1: passthrough to
 * the search service sample-download endpoint. Response envelope includes
 * ``quota_after`` (K-3 default) so the UI can update the QuotaIndicator
 * with a single round-trip.
 *
 * D-13 BLOCKER fix: route accepts either the legacy paste-mode ``apiKey``
 * OR the v0.2 email/password ``buyerPk``. v0.2 sessions resolve via
 * INTERNAL_SEARCH_KEY (see src/lib/buyer-bearer.ts).
 */

import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";

type SampleDownloadResponse = {
  presigned_url: string;
  expires_at: string;
  instance_uid: string;
  study_uid: string;
  size_bytes: number;
  quota_after: {
    used: number;
    limit: number;
    resets_at: string;
  };
};

export const dynamic = "force-dynamic";

export async function POST(
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
  const res = await upstreamFetch<SampleDownloadResponse>(
    bases.search,
    `/v1/studies/${encodeURIComponent(uid)}/sample-download`,
    {
      method: "POST",
      bearer: resolved.bearer,
      headers: actingBuyerHeaders(session, resolved.mode),
      // Empty body — the upstream endpoint takes no parameters today.
      body: {},
    },
  );
  if (!res.ok) {
    const headers: Record<string, string> = {};
    if (res.retryAfter !== undefined && Number.isFinite(res.retryAfter)) {
      headers["Retry-After"] = String(res.retryAfter);
    }
    return NextResponse.json(
      {
        error: res.code,
        detail: res.detail,
        request_id: res.requestId,
      },
      { status: res.status, headers },
    );
  }
  return NextResponse.json(res.data, { status: 200 });
}
