import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ orderId: string }> },
) {
  const session = await getBuyerSession();
  if (!session.apiKey) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "No session" },
      { status: 401 },
    );
  }
  const { orderId } = await params;
  const body = await req.json().catch(() => ({}));
  const res = await upstreamFetch(
    bases.fulfillment,
    `/v1/orders/${orderId}/download-urls`,
    {
      method: "POST",
      bearer: session.apiKey,
      body,
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
