/**
 * RevenueTile {#revenue-tile-v1} — design-spec §17.6 + K-13/K-15.
 *
 * v0.1 contract (K-15 = static dummy, K-13 = ₩ 150,000 form):
 *   - HOSP-001 → ₩ 18,400,000 fixed (matches §18.1 ASCII mock).
 *   - Δ vs last month: +12.3% by default; pass null to hide the delta.
 *   - Hardcoded "시뮬레이션 — v0.2 정산 대기" disclaimer (FR-HO-3.3).
 *
 * The disclaimer is enforced — even if a future caller forgets to pass
 * one, the component falls back to the i18n string. There's deliberately
 * NO `disclaimer` prop that lets callers blank it out.
 */

"use client";

import clsx from "clsx";
import { getDict } from "@/lib/i18n";
import { formatKrw } from "./format";

export type RevenueData = {
  amount_krw: number;
  delta_pct: number | null; // null = first month, render an em-dash
};

export const REVENUE_DUMMY: Record<string, RevenueData> = {
  // K-15: HOSP-001 = ₩18.4M fixed for D-day demo (Kyle decision).
  "HOSP-001": { amount_krw: 18_400_000, delta_pct: 12.3 },
  // HOSP-002 first month — render the empty state.
  "HOSP-002": { amount_krw: 0, delta_pct: null },
};

export function RevenueTile({
  data,
  loading = false,
  testId = "revenue-tile",
}: {
  data: RevenueData | null;
  loading?: boolean;
  testId?: string;
}) {
  const dict = getDict("ko");

  if (loading) {
    return (
      <div data-testid={testId} data-state="loading" className="flex flex-col gap-2">
        <div className="skeleton h-8 w-40" />
        <div className="skeleton h-3 w-32" />
      </div>
    );
  }

  if (!data || data.amount_krw <= 0) {
    return (
      <div
        data-testid={testId}
        data-state="empty"
        className="flex flex-col gap-1"
      >
        <div className="text-3xl font-semibold text-text-strong">—</div>
        <div className="text-xs text-text-muted">
          이번 달 첫 데이터 누적 중
        </div>
        <div className="text-[11px] text-text-muted">
          {dict.hospital.tile.revenueDisclaimer}
        </div>
      </div>
    );
  }

  const delta = data.delta_pct;
  const deltaUp = delta !== null && delta >= 0;

  return (
    <div data-testid={testId} className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="text-3xl font-semibold tabular-nums text-text-strong">
          {formatKrw(data.amount_krw)}
        </span>
        {delta !== null ? (
          <span
            data-testid={`${testId}-delta`}
            className={clsx(
              "text-xs font-medium tabular-nums",
              deltaUp ? "text-teal-700" : "text-red-700",
            )}
          >
            {deltaUp ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}%
          </span>
        ) : null}
      </div>
      <div className="text-xs text-text-muted">{dict.hospital.tile.monthOverMonth}</div>
      <div className="text-[11px] text-text-muted">
        {dict.hospital.tile.revenueDisclaimer}
      </div>
    </div>
  );
}
