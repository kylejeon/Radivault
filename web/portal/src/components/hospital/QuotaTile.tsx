/**
 * QuotaTile {#quota-tile-v1} — design-spec §17.3.
 *
 * 3-up tile (daily / monthly / concurrent). Each progress bar exposes
 * proper ARIA so screen readers announce "X of Y bytes" instead of the
 * raw pixel width. v0.1 = display-only (FR-HO-6 + dev-spec note: limits
 * are not yet enforced server-side).
 */

"use client";

import clsx from "clsx";
import { getDict } from "@/lib/i18n";
import { formatBytes, formatKstDateTime } from "./format";

export type QuotaSegment = {
  bytes_used: number;
  bytes_limit: number;
  resets_at: string | null;
};

export type QuotaData = {
  daily: QuotaSegment | null;     // null = upstream segment failed
  monthly: QuotaSegment | null;
  max_concurrent_uploads: number | null;
};

type Variant = "healthy" | "warn" | "critical";

function variantOf(seg: QuotaSegment | null): Variant {
  if (!seg || seg.bytes_limit <= 0) return "healthy";
  const pct = seg.bytes_used / seg.bytes_limit;
  if (pct >= 0.9) return "critical";
  if (pct >= 0.7) return "warn";
  return "healthy";
}

const BAR_TONE: Record<Variant, string> = {
  healthy: "bg-teal-600",
  warn: "bg-amber-600",
  critical: "bg-red-600",
};

function pct(seg: QuotaSegment | null): number {
  if (!seg || seg.bytes_limit <= 0) return 0;
  return Math.min(100, Math.max(0, (seg.bytes_used / seg.bytes_limit) * 100));
}

function ProgressBar({
  seg,
  ariaLabel,
}: {
  seg: QuotaSegment | null;
  ariaLabel: string;
}) {
  const dict = getDict("ko");
  if (!seg) {
    return (
      <div className="flex h-2 items-center text-xs text-text-muted">
        {dict.hospital.quota.partialFailed}
      </div>
    );
  }
  const v = variantOf(seg);
  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuemin={0}
      aria-valuemax={seg.bytes_limit}
      aria-valuenow={seg.bytes_used}
      className="h-2 w-full overflow-hidden rounded-pill bg-bg-muted"
    >
      <div
        className={clsx("h-full rounded-pill", BAR_TONE[v])}
        style={{ width: `${pct(seg)}%` }}
      />
    </div>
  );
}

function Segment({
  title,
  seg,
  ariaPrefix,
}: {
  title: string;
  seg: QuotaSegment | null;
  ariaPrefix: string;
}) {
  const dict = getDict("ko");
  return (
    <div className="flex flex-1 flex-col gap-1.5">
      <div className="text-xs font-medium text-text-muted">{title}</div>
      <ProgressBar seg={seg} ariaLabel={`${ariaPrefix} ${title}`} />
      {seg ? (
        <div className="text-xs text-text">
          <span className="tabular-nums">{formatBytes(seg.bytes_used)}</span>
          <span className="mx-1 text-text-muted">/</span>
          <span className="tabular-nums">{formatBytes(seg.bytes_limit)}</span>
        </div>
      ) : null}
      {seg ? (
        <div className="text-[11px] text-text-muted">
          {dict.hospital.quota.reset} {formatKstDateTime(seg.resets_at)}
        </div>
      ) : null}
    </div>
  );
}

export function QuotaTile({
  data,
  loading = false,
  error = false,
  testId = "quota-tile",
}: {
  data: QuotaData | null;
  loading?: boolean;
  error?: boolean;
  testId?: string;
}) {
  const dict = getDict("ko");

  if (loading) {
    return (
      <div data-testid={testId} data-state="loading" className="flex gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex flex-1 flex-col gap-1.5">
            <div className="skeleton h-3 w-16" />
            <div className="skeleton h-2 w-full" />
            <div className="skeleton h-3 w-20" />
          </div>
        ))}
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
        {dict.hospital.quota.fetchFailed}
      </div>
    );
  }

  return (
    <div
      data-testid={testId}
      className="flex flex-col gap-3 sm:flex-row sm:items-stretch sm:gap-4"
    >
      <Segment
        title={dict.hospital.quota.daily}
        seg={data.daily}
        ariaPrefix="일일 업로드"
      />
      <Segment
        title={dict.hospital.quota.monthly}
        seg={data.monthly}
        ariaPrefix="월간 업로드"
      />
      <div className="flex flex-1 flex-col gap-1.5">
        <div className="text-xs font-medium text-text-muted">
          {dict.hospital.quota.concurrent}
        </div>
        <div className="text-2xl font-semibold tabular-nums text-text-strong">
          {data.max_concurrent_uploads ?? "—"}
        </div>
        <div className="text-[11px] text-text-muted">
          {dict.hospital.quota.maxConcurrentNote}
        </div>
      </div>
    </div>
  );
}
