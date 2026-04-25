/**
 * CtaPair — design-spec-portal-redesign §5.6 ({#cta-pair-v1}).
 *
 * Reusable primary + secondary button row used by Hero and section CTAs.
 * On mobile the buttons stack `w-full`. The `accent` prop swaps the
 * primary fill from buyer-blue to hospital-teal for the KR Hero (per §5.2).
 */

import Link from "next/link";
import clsx from "clsx";

export type CtaPairProps = {
  primaryLabel: string;
  primaryHref: string;
  secondaryLabel: string;
  secondaryHref: string;
  accent?: "blue" | "teal";
  primaryTestId?: string;
  secondaryTestId?: string;
};

export function CtaPair({
  primaryLabel,
  primaryHref,
  secondaryLabel,
  secondaryHref,
  accent = "blue",
  primaryTestId,
  secondaryTestId,
}: CtaPairProps) {
  const primaryClasses = clsx(
    "inline-flex items-center justify-center rounded-md px-5 py-3 text-base font-medium text-white transition-colors",
    "focus:outline-none focus-visible:ring-4",
    accent === "teal"
      ? "bg-teal-600 hover:bg-teal-700 focus-visible:ring-teal-600/40"
      : "bg-primary-600 hover:bg-primary-700 focus-visible:ring-primary-600/40",
  );
  const secondaryClasses = clsx(
    "inline-flex items-center justify-center rounded-md border border-border-strong bg-bg px-5 py-3 text-base font-medium text-text transition-colors",
    "hover:bg-bg-muted",
    "focus:outline-none focus-visible:ring-4 focus-visible:ring-primary-600/40",
  );

  return (
    <div className="flex flex-col gap-4 mobile:flex-col tablet:flex-row">
      <Link href={primaryHref} className={primaryClasses} data-testid={primaryTestId}>
        {primaryLabel} <span aria-hidden className="ml-2">→</span>
      </Link>
      <Link
        href={secondaryHref}
        className={secondaryClasses}
        data-testid={secondaryTestId}
      >
        {secondaryLabel}
      </Link>
    </div>
  );
}
