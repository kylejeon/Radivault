"use client";

/**
 * <PhiPendingBadge> — text-search-description Phase 1.5 / design-spec §7.
 *
 * Renders a "⚠ pending" indicator in place of the description cell when the
 * scrubbed text is empty (all tokens stripped) or operator review is pending.
 *
 * Note: studies with `preview_status === 'phi_detected'` are excluded from
 * search results entirely (NFR-TS15-COMPLIANCE-2). This component therefore
 * only renders for the "scrubbed but all tokens stripped" case where the
 * row IS visible but the description is unavailable.
 *
 * Variants:
 *   - 'cell' (default) — small inline badge, no background, used inside the
 *     ResultTable description column.
 *   - 'detail' — warning-style block with bg + border-left, used in the
 *     Study Detail metadata grid.
 *
 * Color-blind safe: never relies on color alone — always renders ⚠ icon +
 * text label so deuteranopia / protanopia users still get the meaning.
 */

import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";

export type PhiPendingBadgeProps = {
  variant?: "cell" | "detail";
  locale: Locale;
  className?: string;
};

const COLOR_TEXT_MUTED = "#64748b";
const COLOR_WARNING_LIGHT = "#fffbeb";
const COLOR_WARNING_DARK = "#b45309";

function WarningIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      style={{ flex: "0 0 auto" }}
    >
      <path
        d="M8 1.5L15 14H1L8 1.5Z"
        stroke={color}
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M8 6.5V9.5"
        stroke={color}
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <circle cx="8" cy="11.5" r="0.7" fill={color} />
    </svg>
  );
}

export function PhiPendingBadge({
  variant = "cell",
  locale,
  className,
}: PhiPendingBadgeProps): JSX.Element {
  const t = getDict(locale).search.description;

  if (variant === "detail") {
    return (
      <span
        role="status"
        aria-label={t.phiPendingDetail}
        data-testid="phi-pending-badge"
        data-variant="detail"
        className={className ?? "rv-phi-pending-detail"}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          background: COLOR_WARNING_LIGHT,
          color: COLOR_WARNING_DARK,
          borderLeft: `4px solid ${COLOR_WARNING_DARK}`,
          borderRadius: 4,
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        <WarningIcon size={16} color={COLOR_WARNING_DARK} />
        <span>{t.phiPendingDetail}</span>
      </span>
    );
  }

  // cell variant
  return (
    <span
      role="status"
      aria-label={t.phiPendingCellTooltip}
      title={t.phiPendingCellTooltip}
      data-testid="phi-pending-badge"
      data-variant="cell"
      className={className ?? "rv-phi-pending-cell"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        color: COLOR_TEXT_MUTED,
        fontSize: 12,
        fontStyle: "italic",
      }}
    >
      <WarningIcon size={12} color={COLOR_TEXT_MUTED} />
      <span>{t.phiPendingCell}</span>
    </span>
  );
}
