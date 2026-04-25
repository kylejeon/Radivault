import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { bearerForHospital } from "@/lib/upstream-bearer";
import { getHospitalSession } from "@/lib/session";

export async function GET(req: Request) {
  const session = await getHospitalSession();
  if (!session.hospitalId) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "No hospital session" },
      { status: 401 },
    );
  }
  const bearer = bearerForHospital(session.hospitalId);
  if (!bearer) {
    return NextResponse.json(
      {
        error: "ERR_UPSTREAM_UNAVAILABLE",
        detail: `No upstream bearer configured for ${session.hospitalId}`,
      },
      { status: 503 },
    );
  }
  const url = new URL(req.url);
  const limit = url.searchParams.get("limit") ?? "10";
  const res = await upstreamFetch(bases.fulfillment, "/v1/hospital/me/orders", {
    bearer,
    query: { limit },
  });
  if (!res.ok) {
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  return NextResponse.json(res.data);
}
