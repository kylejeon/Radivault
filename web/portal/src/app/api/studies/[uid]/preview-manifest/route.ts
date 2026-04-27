/**
 * BFF: GET /api/studies/[uid]/preview-manifest
 *
 * dev-spec-jpg-preview-defacing FR-API-2 / §7.2.
 *
 * Pattern parallels the sibling
 * ``/api/studies/[uid]/series/[seriesNum]/frames/[frameNum]/route.ts``
 * — passthrough to the search service preview-manifest endpoint, with
 * the same buyer-bearer resolution and error envelope.
 *
 * Legacy / pre-pipeline study path: when the upstream returns 404 with
 * ``error="manifest_unavailable"`` the BFF passes that 404 through so
 * the design-spec §11.1 silent-coexistence path triggers in
 * ``StudyDetailPanel`` — the existing ``SliceViewerOrFallback`` keeps
 * working, and the new ``FrameSliderViewer`` simply does not mount.
 *
 * Mirrors the auth pattern from the sibling route: ``buyerPk`` (v0.2
 * email/password session) OR legacy ``apiKey``, resolved via
 * ``bearerForBuyer``.
 */

import { bases } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";
import { randomUUID } from "node:crypto";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  context: { params: Promise<{ uid: string }> },
) {
  const session = await getBuyerSession();
  if (!session.buyerPk && !session.apiKey) {
    return new Response(
      JSON.stringify({ error: "ERR_AUTH_EXPIRED", detail: "No session" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }
  const resolved = bearerForBuyer(session);
  if (!resolved.ok) {
    return new Response(
      JSON.stringify({ error: "ERR_AUTH_EXPIRED", detail: resolved.reason }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  const { uid } = await context.params;
  if (!uid || uid.length > 64) {
    return new Response(
      JSON.stringify({
        error: "ERR_VALIDATION",
        detail: "uid must be 1..64 chars",
      }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const requestId = randomUUID();
  const upstreamUrl =
    `${bases.search.replace(/\/$/, "")}` +
    `/v1/studies/${encodeURIComponent(uid)}/preview-manifest`;

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${resolved.bearer}`,
        "X-Request-Id": requestId,
        Accept: "application/json",
        ...actingBuyerHeaders(session, resolved.mode),
      },
      cache: "no-store",
    });
  } catch (err) {
    return new Response(
      JSON.stringify({
        error: "ERR_UPSTREAM_UNAVAILABLE",
        detail: err instanceof Error ? err.message : String(err),
        request_id: requestId,
      }),
      { status: 504, headers: { "Content-Type": "application/json" } },
    );
  }

  // Pass through. 404 from upstream is the explicit "legacy / no
  // manifest" signal that the FrameSliderViewer treats as a
  // mount-skip (design-spec §11.1).
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("Content-Type") ?? "application/json",
      "X-Request-Id": upstream.headers.get("X-Request-Id") ?? requestId,
      // FR-API-2: short cache so a fresh ingest's manifest replaces
      // legacy 404s within ~1 minute.
      "Cache-Control": "private, max-age=60",
    },
  });
}
