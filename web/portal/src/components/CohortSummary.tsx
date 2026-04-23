"use client";

/**
 * Right-pane cohort summary (design-spec §3.4 / FR-A-18).
 *
 * Persistent sidebar with selected study count, total size, and "Review order"
 * CTA. Price is intentionally masked (dev-spec §0.2-3 — v0.1 does not expose
 * ``total_estimated_usd`` in the browser).
 */
export function CohortSummary({
  count,
  totalSizeMb,
  onReview,
  disabled,
}: {
  count: number;
  totalSizeMb: number;
  onReview: () => void;
  disabled?: boolean;
}) {
  return (
    <aside className="card flex flex-col gap-3 p-5" aria-label="Cohort summary">
      <h3 className="text-sm font-medium text-ink-muted">Your cohort</h3>
      <div className="text-3xl font-semibold tabular-nums">
        {count.toLocaleString()}
      </div>
      <div className="text-sm text-ink-subtle">studies selected</div>
      <div className="text-sm">
        <span className="text-ink-muted">Total size</span>{" "}
        <span className="tabular-nums">{totalSizeMb.toFixed(1)} MB</span>
      </div>
      <div className="text-sm">
        <span className="text-ink-muted">Estimated price</span>{" "}
        <span className="text-ink-subtle">— contact for pricing</span>
      </div>
      <button
        type="button"
        onClick={onReview}
        disabled={disabled || count === 0}
        className="mt-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-40"
      >
        Review order ({count})
      </button>
    </aside>
  );
}
