import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { env } from "@/lib/env";
import { getHospitalSession } from "@/lib/session";

/**
 * GET /api/hospital/stats — proxy to central-ingest /v1/hospital/me/stats.
 *
 * The hospital session carries only the hospital_id; the BFF attaches
 * ``HOSPITAL_UPSTREAM_BEARER`` (a gateway auth_token configured by ops) so
 * upstream can resolve the hospital context. In v0.1.5 this will be
 * replaced by a per-session issued token — the BFF shape stays the same.
 */
export async function GET() {
  const session = await getHospitalSession();
  if (!session.hospitalId) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "No hospital session" },
      { status: 401 },
    );
  }
  const bearer = env.hospitalUpstreamBearer;
  if (!bearer) {
    return NextResponse.json(
      {
        error: "ERR_UPSTREAM_UNAVAILABLE",
        detail: "HOSPITAL_UPSTREAM_BEARER not configured",
      },
      { status: 503 },
    );
  }
  const res = await upstreamFetch(bases.central, "/v1/hospital/me/stats", {
    bearer,
  });
  if (!res.ok) {
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  return NextResponse.json(res.data);
}
