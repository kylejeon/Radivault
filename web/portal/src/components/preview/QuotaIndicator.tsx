/**
 * QuotaIndicator — design-spec §10.
 *
 * Three variants:
 *
 *   - "inline" (sidebar) : "Today: N/limit" one-liner.
 *   - "full"   (account) : progress bar + reset countdown.
 *
 * State is driven by props (parent owns the fetch). When the parent has
 * not yet hydrated quota info we render skeleton ellipsis so the layout
 * stays stable.
 */

import clsx from "clsx";
import { getDict, type Locale } from "@/lib/i18n";

export type QuotaState = {
  used: number;
  limit: number;
  resetsAtIso?: string | null;
};

export type QuotaIndicatorProps = {
  state: QuotaState | null | undefined;
  variant?: "inline" | "full";
  locale?: Locale;
  className?: string;
};

function format(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) =>
    String(vars[k] ?? `{${k}}`),
  );
}

export function QuotaIndicator({
  state,
  variant = "inline",
  locale = "en",
  className,
}: QuotaIndicatorProps) {
  const dict = getDict(locale);

  if (variant === "inline") {
    if (!state) {
      return (
        <p
          data-testid="quota-indicator-inline"
          data-state="loading"
          className={clsx("font-mono text-xs text-text-muted", className)}
        >
          {format(dict.quota.todayInline, { used: "…", limit: "1" })}
        </p>
      );
    }
    const exhausted = state.used >= state.limit;
    return (
      <p
        data-testid="quota-indicator-inline"
        data-state={exhausted ? "exhausted" : "ok"}
        className={clsx(
          "font-mono text-xs",
          exhausted ? "text-status-error-fg" : "text-text-muted",
          className,
        )}
      >
        {format(dict.quota.todayInline, {
          used: state.used,
          limit: state.limit,
        })}
        {exhausted ? <> · {dict.quota.resetsAt}</> : null}
      </p>
    );
  }

  // "full" variant — account page progress bar.
  const used = state?.used ?? 0;
  const limit = state?.limit ?? 1;
  const pct = Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  const exhausted = used >= limit;
  return (
    <section
      data-testid="quota-indicator-full"
      data-state={exhausted ? "exhausted" : "ok"}
      role="status"
      aria-live="polite"
      className={clsx(
        "rounded-md border border-border bg-bg p-4",
        className,
      )}
    >
      <h3 className="text-sm font-semibold text-text">
        {dict.quota.sampleDownloadsLabel}
      </h3>
      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full bg-bg-muted"
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={limit}
      >
        <div
          className={clsx(
            "h-full",
            exhausted ? "bg-status-error-fg" : "bg-primary-600",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 font-mono text-xs text-text-muted">
        {format(dict.quota.usedLabel, { used, limit })}
      </p>
      <p className="mt-1 text-[11px] text-text-muted">
        {dict.quota.resetsAt}
      </p>
    </section>
  );
}
