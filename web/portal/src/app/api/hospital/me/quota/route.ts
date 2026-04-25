/**
 * GET /api/hospital/me/quota — FR-HO-14 / FR-INF-7.
 *
 * Proxies central-ingest `GET /v1/hospital/me/quota`. Upstream shape
 * (dev-spec §4.4 FR-INF-7):
 *
 *   {
 *     "hospital_id": "HOSP-001",
 *     "daily":   { "bytes_used", "bytes_limit", "resets_at" },
 *     "monthly": { "bytes_used", "bytes_limit", "resets_at" },
 *     "max_concurrent_uploads": 4,
 *     "ruleset_version": "v0.1.0",
 *     "salt_version": "2026-01",
 *     "pixel_engine_version": "v0.2.0"
 *   }
 *
 * Like the audit-chain-status proxy, the central endpoint is not yet
 * wired; a deterministic stub is returned on 404 / upstream-unavailable
 * with `X-Stubbed: true`. The response is shaped for the portal
 * components (QuotaTile + RulesetVersionBadge), not a passthrough of
 * the upstream — so the portal stays decoupled if central reshapes
 * fields later.
 */

import { NextResponse } from "next/server";
import { bases, upstreamFetch } from "@/lib/upstream";
import { bearerForHospital } from "@/lib/upstream-bearer";
import { getHospitalSession } from "@/lib/session";

type UpstreamSegment = {
  bytes_used: number;
  bytes_limit: number;
  resets_at: string;
};

type UpstreamShape = {
  hospital_id: string;
  daily: UpstreamSegment;
  monthly: UpstreamSegment;
  max_concurrent_uploads: number;
  ruleset_version: string;
  salt_version: string;
  salt_rotate_at?: string;
  pixel_engine_version: string;
};

export type PortalQuotaShape = {
  hospital_id: string;
  daily: { bytes_used: number; bytes_limit: number; resets_at: string };
  monthly: { bytes_used: number; bytes_limit: number; resets_at: string };
  max_concurrent_uploads: number;
  ruleset_version: string;
  salt_version: string;
  salt_rotate_at: string;
  pixel_engine_version: string;
};

function nextKstReset(type: "daily" | "monthly"): string {
  const now = new Date();
  if (type === "daily") {
    const tomorrow = new Date(now);
    tomorrow.setUTCDate(now.getUTCDate() + 1);
    // KST midnight = 15:00 UTC the previous day → 15:00 UTC today.
    tomorrow.setUTCHours(15, 0, 0, 0);
    return tomorrow.toISOString();
  }
  // First of next month, KST midnight.
  const reset = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1, 15, 0, 0),
  );
  return reset.toISOString();
}

function stub(hospitalId: string): PortalQuotaShape {
  const saltRotate = new Date();
  saltRotate.setUTCMonth(saltRotate.getUTCMonth() + 3);
  return {
    hospital_id: hospitalId,
    daily: {
      bytes_used: 123 * 1024 * 1024, // ~123 MB
      bytes_limit: 10 * 1024 * 1024 * 1024, // 10 GB
      resets_at: nextKstReset("daily"),
    },
    monthly: {
      bytes_used: 987 * 1024 * 1024, // ~987 MB
      bytes_limit: 300 * 1024 * 1024 * 1024, // 300 GB
      resets_at: nextKstReset("monthly"),
    },
    max_concurrent_uploads: 4,
    ruleset_version: "v0.1.0",
    salt_version: "2026-01",
    salt_rotate_at: saltRotate.toISOString(),
    pixel_engine_version: "v0.2.0",
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
  const bearer = bearerForHospital(session.hospitalId);
  if (!bearer) {
    const body = stub(session.hospitalId);
    return NextResponse.json(body, { headers: { "X-Stubbed": "true" } });
  }
  const res = await upstreamFetch<UpstreamShape>(
    bases.central,
    "/v1/hospital/me/quota",
    { bearer },
  );
  if (!res.ok) {
    if (res.status === 404 || res.code === "ERR_UPSTREAM_UNAVAILABLE") {
      const body = stub(session.hospitalId);
      return NextResponse.json(body, { headers: { "X-Stubbed": "true" } });
    }
    return NextResponse.json(
      { error: res.code, detail: res.detail, request_id: res.requestId },
      { status: res.status },
    );
  }

  const body: PortalQuotaShape = {
    hospital_id: res.data.hospital_id,
    daily: res.data.daily,
    monthly: res.data.monthly,
    max_concurrent_uploads: res.data.max_concurrent_uploads,
    ruleset_version: res.data.ruleset_version,
    salt_version: res.data.salt_version,
    // Central may or may not surface salt_rotate_at; derive a reasonable
    // placeholder if absent (90d from today) so the badge never shows "—"
    // in production for a happy-path response.
    salt_rotate_at:
      res.data.salt_rotate_at ??
      new Date(Date.now() + 90 * 86400_000).toISOString(),
    pixel_engine_version: res.data.pixel_engine_version,
  };
  return NextResponse.json(body);
}
