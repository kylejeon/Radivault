/**
 * <ModalityDot> — buyer-search-v3 FR-V3-UI-6.
 *
 * 8 px coloured dot for CT/MR/MG/CR/US/PT (6 default colours, "unknown" for
 * NM/OT until v0.1.5).
 */

export type ModalityKey =
  | "CT"
  | "MR"
  | "MG"
  | "CR"
  | "DR"
  | "DX"
  | "US"
  | "PT"
  | string
  | null
  | undefined;

import { HighlightedText } from "./HighlightedText";

export function ModalityDot({
  modality,
  showLabel = true,
  query,
}: {
  modality: ModalityKey;
  showLabel?: boolean;
  query?: string | null;
}) {
  const m = (modality ?? "").toString().toUpperCase();
  const known = ["CT", "MR", "MG", "CR", "DR", "DX", "US", "PT"];
  const cls = known.includes(m) ? m.toLowerCase() : "unknown";
  return (
    <span
      data-testid="modality-dot"
      style={{ display: "inline-flex", alignItems: "center" }}
    >
      <span aria-hidden className={`rv-mod-dot rv-mod-dot--${cls}`} />
      {showLabel ? (
        query ? (
          <HighlightedText html={null} fallback={m || "—"} query={query} />
        ) : (
          <span>{m || "—"}</span>
        )
      ) : null}
    </span>
  );
}
