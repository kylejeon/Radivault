"use client";

/**
 * <MaskedQueryBadge> — text-search-description FR-TS-10 / design-spec §9.
 *
 * Mounts when the search response surfaces ``meta.phi_flagged_patterns``
 * containing at least one match. The badge is informational, not blocking
 * — the search still ran, the buyer's query still hit the database. We
 * only need to telegraph that the audit copy was scrubbed.
 */

import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";
import { useState } from "react";

export type MaskedQueryBadgeProps = {
  flagged: string[];
  locale: Locale;
};

export function MaskedQueryBadge({
  flagged,
  locale,
}: MaskedQueryBadgeProps): JSX.Element | null {
  const [hovered, setHovered] = useState(false);
  if (!flagged || flagged.length === 0) return null;

  const t = getDict(locale).search.searchBar;

  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={t.maskedBadgeText}
      tabIndex={0}
      data-testid="ts-masked-query-badge"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        fontSize: 12,
        fontWeight: 500,
        color: "#b45309", // warning-dark
        background: "#fffbeb", // warning-light
        border: "1px solid #fde68a",
        borderRadius: 999,
        whiteSpace: "nowrap",
        cursor: "help",
      }}
    >
      <span aria-hidden style={{ fontSize: 12 }}>
        {/* Inline triangle so we don't pull a lucide dep just for one icon. */}
        ⚠
      </span>
      <span>{t.maskedBadgeText}</span>
      {hovered ? (
        <span
          role="tooltip"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            zIndex: 60,
            width: 320,
            padding: 12,
            background: "#020617",
            color: "#ffffff",
            fontSize: 12,
            lineHeight: 1.45,
            borderRadius: 8,
            boxShadow:
              "0 10px 25px rgba(15, 23, 42, 0.15), 0 4px 10px rgba(15, 23, 42, 0.10)",
            // Disable the cursor-help on the tooltip itself so users can read
            // it without losing the focus state.
            cursor: "default",
          }}
        >
          {t.maskedBadgeTooltip}
        </span>
      ) : null}
    </span>
  );
}
