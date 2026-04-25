import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ orderId: string }> },
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
  const { orderId } = await params;
  const res = await upstreamFetch(bases.fulfillment, `/v1/orders/${orderId}`, {
    bearer: resolved.bearer,
    headers: actingBuyerHeaders(session, resolved.mode),
  });
  if (!res.ok) {
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  return NextResponse.json(res.data);
}
