/**
 * MetricTile — design-spec-portal-redesign §5.5 ({#metric-tile-v1}).
 *
 * Big-number tile used by the homepage Metrics section. The same
 * component is reused in the v0.3 hospital console (with a sparkline
 * trend prop that is intentionally unused on the homepage to keep
 * the visual quiet).
 */

import clsx from "clsx";

export type MetricTileProps = {
  value: string | number;
  unit?: string;
  label: string;
  sublabel?: string;
  testId?: string;
  className?: string;
};

export function MetricTile({
  value,
  unit,
  label,
  sublabel,
  testId,
  className,
}: MetricTileProps) {
  return (
    <div
      data-testid={testId}
      className={clsx(
        "flex flex-col gap-2 rounded-lg border border-border bg-bg p-6 shadow-card",
        className,
      )}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-5xl font-bold tabular-nums text-primary-600">
          {value}
        </span>
        {unit && (
          <span className="text-base font-medium text-text-muted">{unit}</span>
        )}
      </div>
      <span className="text-sm font-semibold text-text">{label}</span>
      {sublabel && (
        <span className="text-xs text-text-muted">{sublabel}</span>
      )}
    </div>
  );
}
