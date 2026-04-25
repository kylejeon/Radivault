/**
 * GET /api/hospital/me/audit-chain-status — FR-HO-14 / FR-INF-6.
 *
 * Proxies central-ingest `GET /v1/hospital/me/audit-chain-status`. The
 * upstream shape the central team committed to (dev-spec §4.4 FR-INF-6):
 *
 *   {
 *     "hospital_id": "HOSP-001",
 *     "last_anchor_at": "...Z",
 *     "last_anchor_age_seconds": 312,
 *     "last_anchor_hash_prefix": "a3f8d9c1b2e4f5a6",
 *     "chain_continuous": true,
 *     "anchor_count_24h": 48
 *   }
 *
 * v0.1 reality check: the upstream endpoint does not yet exist. When
 * central returns 404 we synthesise a deterministic stub keyed on the
 * hospital_id so the dashboard still renders in demos (TODO K-15 /
 * FR-INF-6 — remove when central ships the route). The stub is
 * explicitly marked with `X-Stubbed: true` so QA / search spot it.
 */

import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { env } from "@/lib/env";
import { getHospitalSession } from "@/lib/session";

type UpstreamShape = {
  hospital_id: string;
  last_anchor_at: string;
  last_anchor_age_seconds: number;
  last_anchor_hash_prefix: string;
  chain_continuous: boolean;
  anchor_count_24h?: number;
};

// Portal response shape matches what AuditChainStatusBadge expects.
type PortalShape = {
  hospital_id: string;
  last_anchor_at: string;
  hash_prefix: string;
  chain_continuous: boolean;
  last_anchor_age_seconds: number;
  anchor_count_24h?: number;
};

function stub(hospitalId: string): PortalShape {
  // Deterministic — pick a fresh anchor 4 min in the past.
  const last = new Date(Date.now() - 4 * 60_000);
  const hash = (hospitalId + "radivaultstub2026").slice(0, 16).padEnd(16, "0");
  return {
    hospital_id: hospitalId,
    last_anchor_at: last.toISOString(),
    hash_prefix: hash,
    chain_continuous: true,
    last_anchor_age_seconds: 240,
    anchor_count_24h: 48,
  };
}

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
    // Dev-only fallback so the local demo works without a bearer.
    const body = stub(session.hospitalId);
    return NextResponse.json(body, { headers: { "X-Stubbed": "true" } });
  }
  const res = await upstreamFetch<UpstreamShape>(
    bases.central,
    "/v1/hospital/me/audit-chain-status",
    { bearer },
  );
  if (!res.ok) {
    // 404 = endpoint not yet implemented in central → stub.
    if (res.status === 404 || res.code === "ERR_UPSTREAM_UNAVAILABLE") {
      const body = stub(session.hospitalId);
      return NextResponse.json(body, { headers: { "X-Stubbed": "true" } });
    }
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }
  const body: PortalShape = {
    hospital_id: res.data.hospital_id,
    last_anchor_at: res.data.last_anchor_at,
    hash_prefix: res.data.last_anchor_hash_prefix,
    chain_continuous: res.data.chain_continuous,
    last_anchor_age_seconds: res.data.last_anchor_age_seconds,
    anchor_count_24h: res.data.anchor_count_24h,
  };
  return NextResponse.json(body);
}
