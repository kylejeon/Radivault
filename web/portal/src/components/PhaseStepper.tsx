import clsx from "clsx";

export type BuyerPhase =
  | "accepted"
  | "fetching_from_hospital"
  | "preparing_download"
  | "ready_to_download"
  | "completed"
  | "cancelled"
  | "expired"
  | "failed";

const HAPPY_PATH: { key: BuyerPhase; label: string }[] = [
  { key: "accepted", label: "Accepted" },
  { key: "fetching_from_hospital", label: "Fetching from hospital" },
  { key: "preparing_download", label: "Preparing download" },
  { key: "ready_to_download", label: "Ready to download" },
  { key: "completed", label: "Completed" },
];

const TERMINAL_ERRORS: BuyerPhase[] = ["cancelled", "expired", "failed"];

/**
 * 5-phase horizontal stepper (design-spec §3.5 / FR-A-42).
 *
 * Unhappy paths (cancelled/expired/failed) replace the tracker with a single
 * red pill so the operator immediately knows the happy path is over.
 */
export function PhaseStepper({ phase }: { phase: BuyerPhase }) {
  if (TERMINAL_ERRORS.includes(phase)) {
    return (
      <div
        role="status"
        className="rounded-md bg-red-50 px-4 py-2 text-sm font-medium text-danger"
      >
        Order {phase}. Contact support@radivault.io if unexpected.
      </div>
    );
  }
  const idx = HAPPY_PATH.findIndex((p) => p.key === phase);
  return (
    <ol
      className="flex items-center gap-2"
      aria-label="Order phase"
    >
      {HAPPY_PATH.map((p, i) => {
        const reached = i <= idx;
        return (
          <li key={p.key} className="flex flex-1 items-center gap-2">
            <span
              className={clsx(
                "phase-dot",
                reached ? p.key : "accepted",
                !reached && "opacity-30",
              )}
              aria-hidden
            />
            <span
              className={clsx(
                "text-xs",
                i === idx ? "font-semibold text-ink" : "text-ink-subtle",
              )}
            >
              {p.label}
            </span>
            {i < HAPPY_PATH.length - 1 ? (
              <span
                className={clsx(
                  "h-px flex-1",
                  reached ? "bg-primary" : "bg-surface-border",
                )}
                aria-hidden
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
