import clsx from "clsx";

/**
 * TileCard — the 6 Hospital Dashboard tiles (design-spec §6).
 *
 * Accepts a large headline number + subtitle + optional footer (e.g.
 * "simulation only" disclaimer on B-2). Layout is 1-scroll, 2x3 grid.
 */
export function TileCard({
  title,
  value,
  subtitle,
  footer,
  tone = "neutral",
  children,
}: {
  title: string;
  value?: React.ReactNode;
  subtitle?: React.ReactNode;
  footer?: React.ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
  children?: React.ReactNode;
}) {
  const toneClass = {
    neutral: "",
    success: "ring-1 ring-success/40",
    warning: "ring-1 ring-warning/60",
    danger: "ring-1 ring-danger/50",
  }[tone];
  return (
    <section
      className={clsx("card flex flex-col gap-3 p-5", toneClass)}
      aria-label={title}
    >
      <header className="flex items-start justify-between">
        <h3 className="text-sm font-medium text-ink-muted">{title}</h3>
      </header>
      {value !== undefined ? (
        <div className="text-3xl font-semibold tabular-nums text-ink">
          {value}
        </div>
      ) : null}
      {subtitle ? (
        <div className="text-sm text-ink-subtle">{subtitle}</div>
      ) : null}
      {children}
      {footer ? (
        <footer className="mt-auto text-xs text-ink-subtle">{footer}</footer>
      ) : null}
    </section>
  );
}
