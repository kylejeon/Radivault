/**
 * BFF: GET /api/studies/[uid]/thumbnail
 *
 * dev-spec-buyer-browse-preview FR-API-2: passthrough to the search service
 * preview thumbnail endpoint. Streams JPEG bytes back to the client with
 * the upstream Cache-Control + ETag headers preserved so the browser/CDN
 * can revalidate independently.
 *
 * D-13 BLOCKER fix: route accepts either the legacy paste-mode ``apiKey``
 * OR the v0.2 email/password ``buyerPk``. v0.2 sessions resolve via
 * INTERNAL_SEARCH_KEY (see src/lib/buyer-bearer.ts). Operator must set
 * the env var or the route falls through to a 401 with detail
 * `no_internal_key`.
 */

import { bases } from "@/lib/upstream";
import { env } from "@/lib/env";
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
  const requestId = randomUUID();
  const upstreamUrl = `${bases.search.replace(/\/$/, "")}/v1/studies/${encodeURIComponent(uid)}/thumbnail`;

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${resolved.bearer}`,
        "X-Request-Id": requestId,
        Accept: "image/jpeg",
        ...actingBuyerHeaders(session, resolved.mode),
      },
      // Disable Next's automatic fetch cache — we want the browser/CDN
      // layer (via Cache-Control header) to do the caching, not the
      // BFF process.
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

  if (!upstream.ok) {
    const body = await upstream.text();
    return new Response(body || JSON.stringify({ error: "ERR_HTTP" }), {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("Content-Type") ?? "application/json",
        "X-Request-Id":
          upstream.headers.get("X-Request-Id") ?? requestId,
      },
    });
  }

  // Stream JPEG bytes back. Preserve Cache-Control + ETag so the browser
  // can revalidate. We don't add CDN-level caching here (that's a layer
  // upstream of the BFF — Vercel edge / Cloudflare). The Cache-Control
  // value of "public, max-age=86400, immutable" comes from the search
  // router and is the canonical source for this surface.
  const headers = new Headers();
  headers.set("Content-Type", upstream.headers.get("Content-Type") ?? "image/jpeg");
  const cacheControl = upstream.headers.get("Cache-Control");
  if (cacheControl) headers.set("Cache-Control", cacheControl);
  const etag = upstream.headers.get("ETag");
  if (etag) headers.set("ETag", etag);
  const len = upstream.headers.get("Content-Length");
  if (len) headers.set("Content-Length", len);
  headers.set(
    "X-Request-Id",
    upstream.headers.get("X-Request-Id") ?? requestId,
  );

  // env import keeps this file from being tree-shaken into a client bundle
  // (env throws if accessed during build outside server context).
  void env.searchUrl;

  return new Response(upstream.body, { status: 200, headers });
}
