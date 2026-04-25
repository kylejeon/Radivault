/**
 * ModalityDistributionChart {#modality-dist-v1} — design-spec §17.5.
 *
 * 200×200 SVG donut. Color tokens are inherited from §11.1 (the
 * `.badge-modality-tint.*` ladder) so a CT slice in the donut matches a
 * CT chip in the buyer's StudyCard. WCAG-AA verified by FR-BP-5.
 *
 * a11y:
 *   - <title> + <desc> SVG nodes describe the chart.
 *   - Each <path> ships an aria-label with the modality + count + %.
 *   - The donut center has the total study count for at-a-glance reading.
 */

"use client";

import { getDict } from "@/lib/i18n";

export type ModalitySlice = {
  modality: string;
  count: number;
};

const MODALITY_FILL: Record<string, string> = {
  CT: "#1d4ed8",   // blue-700
  MR: "#6d28d9",   // violet-700
  MG: "#9d174d",   // pink-800 (WCAG-bumped)
  CR: "#15803d",   // green-700
  DR: "#15803d",
  DX: "#15803d",
  PT: "#b91c1c",   // red-700
  US: "#c2410c",   // orange-700
  XA: "#475569",   // slate-600
  UNKNOWN: "#94a3b8",
};

function fillOf(modality: string): string {
  return MODALITY_FILL[modality.toUpperCase()] ?? MODALITY_FILL.UNKNOWN;
}

function arcPath(cx: number, cy: number, r: number, startRad: number, endRad: number): string {
  const x1 = cx + r * Math.cos(startRad);
  const y1 = cy + r * Math.sin(startRad);
  const x2 = cx + r * Math.cos(endRad);
  const y2 = cy + r * Math.sin(endRad);
  const largeArc = endRad - startRad > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
}

export function ModalityDistributionChart({
  slices,
  loading = false,
  testId = "modality-distribution-chart",
}: {
  slices: ModalitySlice[];
  loading?: boolean;
  testId?: string;
}) {
  const dict = getDict("ko");

  if (loading) {
    return (
      <div
        data-testid={testId}
        data-state="loading"
        className="flex h-44 items-center justify-center"
      >
        <div className="size-32 animate-pulse rounded-full bg-bg-muted" />
      </div>
    );
  }

  const total = slices.reduce((sum, s) => sum + Math.max(0, s.count), 0);

  if (total === 0) {
    return (
      <div
        data-testid={testId}
        data-state="empty"
        className="flex h-44 flex-col items-center justify-center gap-2"
      >
        <div className="size-24 rounded-full bg-bg-muted" />
        <span className="text-xs text-text-muted">
          {dict.hospital.tile.modalityNoData}
        </span>
      </div>
    );
  }

  // SVG geometry — 200×200, donut radius 80 outer / 50 inner.
  const cx = 100;
  const cy = 100;
  const rOuter = 80;
  const rInner = 50;

  let cursor = -Math.PI / 2; // start at 12 o'clock

  return (
    <div
      data-testid={testId}
      className="flex flex-col gap-3 sm:flex-row sm:items-center"
    >
      <svg
        role="img"
        aria-label="Modality 분포 도넛 차트"
        viewBox="0 0 200 200"
        width="160"
        height="160"
      >
        <title>Modality 분포 도넛 차트</title>
        <desc>
          전체 study {total.toLocaleString("ko-KR")} 건의 모달리티 비중.
        </desc>
        {slices.map((s) => {
          const angle = (s.count / total) * Math.PI * 2;
          const start = cursor;
          const end = cursor + angle;
          cursor = end;
          const pct = ((s.count / total) * 100).toFixed(1);
          return (
            <path
              key={s.modality}
              d={arcPath(cx, cy, rOuter, start, end)}
              fill={fillOf(s.modality)}
              aria-label={`${s.modality} ${s.count} 건 (${pct} %)`}
            />
          );
        })}
        {/* Inner cutout for the donut hole. */}
        <circle cx={cx} cy={cy} r={rInner} fill="white" />
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          className="fill-text-strong"
          fontSize="22"
          fontWeight="600"
        >
          {total.toLocaleString("ko-KR")}
        </text>
        <text
          x={cx}
          y={cy + 14}
          textAnchor="middle"
          className="fill-text-muted"
          fontSize="11"
        >
          studies
        </text>
      </svg>
      <ul className="flex flex-col gap-1 text-xs">
        {slices.map((s) => (
          <li key={s.modality} className="flex items-center gap-2">
            <span
              aria-hidden
              className="inline-block size-2.5 rounded-sm"
              style={{ background: fillOf(s.modality) }}
            />
            <span className="w-8 font-medium uppercase">{s.modality}</span>
            <span className="tabular-nums text-text-muted">
              {s.count.toLocaleString("ko-KR")}
            </span>
            <span className="tabular-nums text-text-muted">
              ({((s.count / total) * 100).toFixed(0)}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
