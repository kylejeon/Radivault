/**
 * BFF: GET /api/studies/[uid]/series/[seriesNum]/frames/[frameNum]
 *
 * dev-spec-buyer-browse-preview FR-API-2: passthrough to the search service
 * preview-frame endpoint. Streams JPEG bytes with upstream cache headers.
 */

import { bases } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { randomUUID } from "node:crypto";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  context: {
    params: Promise<{
      uid: string;
      seriesNum: string;
      frameNum: string;
    }>;
  },
) {
  const session = await getBuyerSession();
  if (!session.buyerPk && !session.apiKey) {
    return new Response(
      JSON.stringify({ error: "ERR_AUTH_EXPIRED", detail: "No session" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }
  if (!session.apiKey) {
    return new Response(
      JSON.stringify({
        error: "ERR_AUTH_EXPIRED",
        detail:
          "Session has no API key — paste-mode signin required for preview surface.",
      }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  const { uid, seriesNum, frameNum } = await context.params;
  const seriesN = Number.parseInt(seriesNum, 10);
  const frameN = Number.parseInt(frameNum, 10);
  if (
    !Number.isFinite(seriesN) ||
    seriesN < 1 ||
    !Number.isFinite(frameN) ||
    frameN < 1
  ) {
    return new Response(
      JSON.stringify({
        error: "ERR_VALIDATION",
        detail: "series_num and frame_num must be positive integers",
      }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const requestId = randomUUID();
  const upstreamUrl =
    `${bases.search.replace(/\/$/, "")}` +
    `/v1/studies/${encodeURIComponent(uid)}/series/${seriesN}/frames/${frameN}`;

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${session.apiKey}`,
        "X-Request-Id": requestId,
        Accept: "image/jpeg",
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

  return new Response(upstream.body, { status: 200, headers });
}
