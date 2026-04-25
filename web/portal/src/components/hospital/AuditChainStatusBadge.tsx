/**
 * AuditChainStatusBadge {#audit-chain-status-v1} — design-spec §17.1.
 *
 * Pill (64 px tall) shown both inline (header) and as the body of tile #4
 * on the 9-tile dashboard. Variants:
 *   - ok      — chain_continuous = true AND last_anchor_age < 1h
 *   - stale   — chain_continuous = true AND last_anchor_age >= 1h
 *   - broken  — chain_continuous = false  (any age)
 *
 * Color is never the only signal (FR-NFR / WCAG): each variant ships a
 * shape glyph (✓ / ⚠ / ✕). The badge sets `role="status"` +
 * `aria-live="polite"` so screen readers announce status changes when the
 * dashboard polls every minute.
 */

"use client";

import clsx from "clsx";
import { getDict } from "@/lib/i18n";
import { formatKstTime } from "./format";

export type AuditChainStatusData = {
  last_anchor_at: string | null;
  hash_prefix: string | null;
  chain_continuous: boolean;
  last_anchor_age_seconds?: number | null;
};

type Variant = "ok" | "stale" | "broken";

function deriveVariant(data: AuditChainStatusData | null): Variant | null {
  if (!data) return null;
  if (!data.chain_continuous) return "broken";
  // Prefer the upstream-provided age; fall back to client-side delta.
  const ageSec =
    typeof data.last_anchor_age_seconds === "number"
      ? data.last_anchor_age_seconds
      : data.last_anchor_at
        ? Math.max(0, (Date.now() - new Date(data.last_anchor_at).getTime()) / 1000)
        : Number.POSITIVE_INFINITY;
  return ageSec >= 3600 ? "stale" : "ok";
}

const VARIANT_TONE: Record<Variant, { dot: string; ring: string; glyph: string }> = {
  ok: {
    dot: "bg-teal-600",
    ring: "ring-teal-200",
    glyph: "✓",
  },
  stale: {
    dot: "bg-amber-600",
    ring: "ring-amber-200",
    glyph: "⚠",
  },
  broken: {
    dot: "bg-red-600",
    ring: "ring-red-200",
    glyph: "✕",
  },
};

export function AuditChainStatusBadge({
  data,
  loading = false,
  error = false,
  testId = "audit-chain-status-badge",
}: {
  data: AuditChainStatusData | null;
  loading?: boolean;
  error?: boolean;
  testId?: string;
}) {
  const dict = getDict("ko");

  if (loading) {
    return (
      <div
        data-testid={testId}
        data-state="loading"
        role="status"
        aria-live="polite"
        className="flex h-16 items-center gap-3 rounded-pill bg-bg-muted px-4"
      >
        <span className="skeleton inline-block size-2.5 rounded-full" />
        <div className="flex flex-col gap-1">
          <span className="skeleton inline-block h-3 w-32" />
          <span className="skeleton inline-block h-3 w-40" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        data-testid={testId}
        data-state="error"
        role="status"
        aria-live="polite"
        className="flex h-16 items-center gap-3 rounded-pill bg-bg-muted px-4 text-sm text-text-muted"
      >
        <span aria-hidden className="inline-block size-2.5 rounded-full bg-slate-400" />
        <span>{dict.hospital.auditChain.retry}</span>
      </div>
    );
  }

  const variant = deriveVariant(data) ?? "ok";
  const tone = VARIANT_TONE[variant];
  const labelKo = {
    ok: dict.hospital.auditChain.ok,
    stale: dict.hospital.auditChain.stale,
    broken: dict.hospital.auditChain.broken,
  }[variant];

  return (
    <div
      data-testid={testId}
      data-variant={variant}
      role="status"
      aria-live="polite"
      className={clsx(
        "flex h-16 items-center gap-3 rounded-pill bg-white px-4 ring-2",
        tone.ring,
      )}
    >
      <span
        aria-hidden
        className={clsx("inline-block size-2.5 rounded-full", tone.dot)}
      />
      <span aria-hidden className="text-base font-semibold text-text-strong">
        {tone.glyph}
      </span>
      <div className="flex flex-col leading-tight">
        <span className="text-xs font-medium text-text-muted">
          {dict.hospital.auditChain.lastAnchor} {formatKstTime(data.last_anchor_at)} KST · {labelKo}
        </span>
        <code
          data-testid={`${testId}-hash`}
          className="font-mono text-xs text-text"
        >
          {(data.hash_prefix ?? "—").slice(0, 16)}
        </code>
      </div>
    </div>
  );
}
