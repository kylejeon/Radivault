import { NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";

// FR-A-32: deterministic v0.1 stub for the agreement hash. Production will
// replace this with a signed MSA digest once billing v0.2 lands.
const STUB_AGREEMENT_HASH = createHash("sha256")
  .update("rv-v0.1-msa-stub")
  .digest("hex");

export async function GET() {
  const session = await getBuyerSession();
  if (!session.apiKey) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "No session" },
      { status: 401 },
    );
  }
  const res = await upstreamFetch(bases.fulfillment, "/v1/orders", {
    bearer: session.apiKey,
  });
  if (!res.ok) {
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  return NextResponse.json(res.data);
}

export async function POST(req: Request) {
  const session = await getBuyerSession();
  if (!session.apiKey) {
    return NextResponse.json(
      { error: "ERR_AUTH_EXPIRED", detail: "No session" },
      { status: 401 },
    );
  }
  const body = (await req.json().catch(() => ({}))) as {
    pseudo_study_uids?: string[];
    notes?: string;
  };
  const idemKey = req.headers.get("Idempotency-Key") ?? crypto.randomUUID();
  const res = await upstreamFetch(bases.fulfillment, "/v1/orders", {
    method: "POST",
    bearer: session.apiKey,
    headers: { "Idempotency-Key": idemKey },
    body: {
      pseudo_study_uids: body.pseudo_study_uids ?? [],
      agreement_hash: STUB_AGREEMENT_HASH,
      notes: body.notes,
    },
  });
  if (!res.ok) {
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  return NextResponse.json(res.data, { status: 202 });
}
