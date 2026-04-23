import clsx from "clsx";

const KNOWN = new Set(["CT", "MR", "CR", "DR", "MG", "US", "PT"]);

/** Modality colour chip — design-spec §4.3 / FR-A-23. */
export function ModalityBadge({ modality }: { modality: string | null | undefined }) {
  const m = (modality ?? "").toUpperCase();
  const cls = KNOWN.has(m) ? m.toLowerCase() : "unknown";
  return (
    <span className={clsx("badge-modality", cls)} aria-label={`Modality ${m || "unknown"}`}>
      {m || "—"}
    </span>
  );
}
