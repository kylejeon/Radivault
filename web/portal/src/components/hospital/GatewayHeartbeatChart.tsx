/**
 * GatewayHeartbeatChart {#gateway-heartbeat-v1} — design-spec §17.2.
 *
 * 24h sparkline rendered as 288 stripes (5-minute buckets). Pure inline
 * SVG — no Recharts — to keep the tile under the §17 size budget and to
 * avoid pulling a charting dep just for one component (FR-HO-3.5,
 * FR-HO-4 give the dev-spec choice "Recharts OR pure SVG").
 *
 * Variant resolution:
 *   - online   — last_sync_at within 5 min   (teal)
 *   - warning  — last_sync_at within 30 min  (amber)
 *   - offline  — older / unknown             (red)
 */

"use client";

import clsx from "clsx";
import { getDict } from "@/lib/i18n";
import { formatRelativeKo } from "./format";

export type GatewayBucket = {
  ts: string;       // ISO8601 — start of the 5-minute bucket
  status: "ok" | "warn" | "miss";
};

export type GatewayHeartbeatData = {
  status: "online" | "warning" | "offline" | "unknown";
  last_sync_at: string | null;
  last_sync_delta_seconds: number | null;
  buckets_24h?: GatewayBucket[];
};

const STRIPE_COUNT = 288; // 24h / 5m
const STRIPE_FILL: Record<GatewayBucket["status"], string> = {
  ok: "#0d9488",   // hospital teal-600
  warn: "#d97706", // amber-600
  miss: "#cbd5e1", // slate-300 (no signal — neutral)
};

const STATUS_TONE: Record<
  GatewayHeartbeatData["status"],
  { dot: string; label: "online" | "warning" | "offline" | "unknown" }
> = {
  online: { dot: "bg-teal-600", label: "online" },
  warning: { dot: "bg-amber-600", label: "warning" },
  offline: { dot: "bg-red-600", label: "offline" },
  unknown: { dot: "bg-slate-400", label: "unknown" },
};

function deriveBuckets(data: GatewayHeartbeatData): GatewayBucket[] {
  if (data.buckets_24h && data.buckets_24h.length > 0) {
    return data.buckets_24h.slice(-STRIPE_COUNT);
  }
  // Fallback synthetic stripes — last bucket reflects current status, the rest
  // are "ok" so a healthy hospital does not look like it spent 24h offline.
  const out: GatewayBucket[] = [];
  for (let i = 0; i < STRIPE_COUNT; i++) {
    out.push({ ts: `bucket-${i}`, status: "ok" });
  }
  if (data.status === "warning") out[out.length - 1] = { ts: "now", status: "warn" };
  if (data.status === "offline") out[out.length - 1] = { ts: "now", status: "miss" };
  return out;
}

const STATUS_LABEL_KO: Record<GatewayHeartbeatData["status"], string> = {
  online: "정상",
  warning: "주의",
  offline: "연결 끊김",
  unknown: "확인 중",
};

export function GatewayHeartbeatChart({
  data,
  loading = false,
  error = false,
  testId = "gateway-heartbeat-chart",
}: {
  data: GatewayHeartbeatData | null;
  loading?: boolean;
  error?: boolean;
  testId?: string;
}) {
  const dict = getDict("ko");

  if (loading) {
    return (
      <div data-testid={testId} data-state="loading" className="flex flex-col gap-2">
        <div className="skeleton h-3 w-24" />
        <div className="skeleton h-12 w-full" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div
        data-testid={testId}
        data-state="error"
        className="flex h-12 items-center justify-center rounded-md bg-bg-muted text-sm text-text-muted"
      >
        Gateway 신호 조회 실패
      </div>
    );
  }
  // Empty state: gateway never installed → status="unknown" + no buckets.
  if (data.status === "unknown" && !data.last_sync_at) {
    return (
      <div
        data-testid={testId}
        data-state="empty"
        className="flex h-12 items-center justify-center rounded-md bg-bg-muted text-sm text-text-muted"
      >
        {dict.hospital.tile.gatewayDisconnected}
      </div>
    );
  }

  const tone = STATUS_TONE[data.status];
  const buckets = deriveBuckets(data);
  const stripeWidth = 240 / STRIPE_COUNT;

  return (
    <div data-testid={testId} data-variant={tone.label} className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-medium text-text">
          <span aria-hidden className={clsx("inline-block size-2.5 rounded-full", tone.dot)} />
          {STATUS_LABEL_KO[data.status]}
        </span>
        <span className="text-xs text-text-muted">
          {dict.hospital.tile.lastSignal} {formatRelativeKo(data.last_sync_at)}
        </span>
      </div>
      <svg
        role="img"
        aria-label="24시간 Gateway heartbeat 스파크라인"
        viewBox="0 0 240 48"
        width="100%"
        height="48"
        preserveAspectRatio="none"
      >
        <title>24시간 Gateway heartbeat 스파크라인</title>
        <desc>
          최근 24시간 5분 bucket × 288 stripe. 정상=teal, 주의=amber, 미수신=회색.
        </desc>
        {buckets.map((b, i) => (
          <rect
            key={`${b.ts}-${i}`}
            x={i * stripeWidth}
            y={0}
            width={Math.max(0.4, stripeWidth - 0.2)}
            height={48}
            fill={STRIPE_FILL[b.status]}
          />
        ))}
      </svg>
    </div>
  );
}
