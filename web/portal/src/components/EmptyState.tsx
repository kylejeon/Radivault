import Link from "next/link";

/** Empty / error / offline banner (design-spec §7). */
export function EmptyState({
  title,
  body,
  ctaHref,
  ctaLabel,
}: {
  title: string;
  body?: string;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-12 text-center">
      <h3 className="text-lg font-semibold text-ink">{title}</h3>
      {body ? <p className="max-w-prose text-sm text-ink-muted">{body}</p> : null}
      {ctaHref && ctaLabel ? (
        <Link
          href={ctaHref}
          className="mt-1 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
        >
          {ctaLabel}
        </Link>
      ) : null}
    </div>
  );
}
