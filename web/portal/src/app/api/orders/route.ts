import { NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { bases, upstreamFetch } from "@/lib/upstream";
import { getBuyerSession } from "@/lib/session";
import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";

// FR-A-32: deterministic v0.1 stub for the agreement hash. Production will
// replace this with a signed MSA digest once billing v0.2 lands.
const STUB_AGREEMENT_HASH = createHash("sha256")
  .update("rv-v0.1-msa-stub")
  .digest("hex");

export async function GET() {
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
  const res = await upstreamFetch(bases.fulfillment, "/v1/orders", {
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

export async function POST(req: Request) {
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
  const body = (await req.json().catch(() => ({}))) as {
    pseudo_study_uids?: string[];
    allowed_hospitals?: string[];
    notes?: string;
  };
  const idemKey = req.headers.get("Idempotency-Key") ?? crypto.randomUUID();
  // FR-BP-9 / AC-BP-8 (HIGH-4 fix): forward the cohort-derived hospital
  // scope to fulfillment so federated cohort orders fan out only to the
  // hospitals already represented in the cohort. Drop empty / non-string
  // entries defensively — fulfillment treats `[]` as "any hospital" which
  // is the wrong default for federated AC scoping.
  const allowedHospitals = Array.from(
    new Set(
      (body.allowed_hospitals ?? [])
        .filter((h): h is string => typeof h === "string" && h.length > 0),
    ),
  ).sort();
  const res = await upstreamFetch(bases.fulfillment, "/v1/orders", {
    method: "POST",
    bearer: resolved.bearer,
    headers: {
      "Idempotency-Key": idemKey,
      ...actingBuyerHeaders(session, resolved.mode),
    },
    body: {
      pseudo_study_uids: body.pseudo_study_uids ?? [],
      ...(allowedHospitals.length > 0
        ? { allowed_hospitals: allowedHospitals }
        : {}),
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
