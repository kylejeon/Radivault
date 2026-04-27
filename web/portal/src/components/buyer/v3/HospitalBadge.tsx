/**
 * <HospitalBadge> — buyer-search-v3 FR-V3-UI-5.
 *
 * Renders a region-pseudo pill ("● SEOUL-A") in a region-specific colour.
 * Two variants: ``badge`` (default — pill with text) and ``dot`` (4 px stripe
 * for the result-table left edge).
 */

import { HighlightedText } from "./HighlightedText";

export type HospitalBadgeVariant = "badge" | "dot";

export type HospitalBadgeProps = {
  regionPseudo: string | null | undefined;
  variant?: HospitalBadgeVariant;
  query?: string | null;
};

function regionKey(regionPseudo: string | null | undefined): string {
  if (!regionPseudo) return "unknown";
  const head = regionPseudo.split("-")[0]?.toLowerCase() ?? "unknown";
  return head;
}

export function HospitalBadge({
  regionPseudo,
  variant = "badge",
  query,
}: HospitalBadgeProps) {
  const key = regionKey(regionPseudo);
  if (variant === "dot") {
    // Used inside ResultTable as the per-row stripe — no text, just colour.
    return (
      <span
        aria-hidden
        data-testid="hospital-badge-dot"
        className={`rv-col-stripe rv-col-stripe--${key}`}
      />
    );
  }
  return (
    <span
      data-testid="hospital-badge"
      className={`rv-hospital-badge rv-hospital-badge--${key}`}
    >
      <span className="rv-hospital-badge__dot" />
      {query ? (
        <HighlightedText html={null} fallback={regionPseudo ?? "—"} query={query} />
      ) : (
        <span>{regionPseudo ?? "—"}</span>
      )}
    </span>
  );
}
