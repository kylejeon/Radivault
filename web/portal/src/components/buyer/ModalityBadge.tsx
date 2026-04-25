import clsx from "clsx";

/**
 * ModalityBadge {#modality-badge-v1} — design-spec-portal-redesign §11.1.
 * FR-BP-4, FR-BP-5.
 *
 * Tinted DataTable badge (lighter bg + dark fg) used inside `/search` rows,
 * `/studies/[id]` metadata grid, and `/orders/new` cohort items. Distinct
 * from the legacy `<components/ModalityBadge>` (filled saturated chip), which
 * is kept for the older buyer-portal-demo surfaces.
 *
 * 7 variants — CT / MR / MG / CR / DX / PT / US — plus an `unknown` fallback
 * for unrecognised modalities (XA, NM, …). Colours come from `globals.css`
 * (`.badge-modality-tint.*`) and are WCAG AA-verified per FR-BP-5.
 */

const KNOWN_VARIANTS = new Set([
  "CT",
  "MR",
  "MG",
  "CR",
  "DX",
  "DR",
  "PT",
  "US",
  "XA",
]);

export function BuyerModalityBadge({
  modality,
  size = "md",
}: {
  modality: string | null | undefined;
  size?: "sm" | "md";
}) {
  const raw = (modality ?? "").toUpperCase();
  const variant = KNOWN_VARIANTS.has(raw) ? raw.toLowerCase() : "unknown";
  const label = raw || "—";
  return (
    <span
      data-testid={`modality-badge-${variant}`}
      className={clsx(
        "badge-modality-tint",
        variant,
        size === "sm" ? "px-1.5 text-[10px]" : "",
      )}
      aria-label={`modality: ${label}`}
    >
      {label}
    </span>
  );
}
