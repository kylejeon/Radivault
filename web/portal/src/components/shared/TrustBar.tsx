/**
 * TrustBar — design-spec-portal-redesign §5.3 ({#trust-bar-v1}).
 *
 * Compliance status ladder. Replaces the customer-logo wall that the
 * homepage cannot render until pilot hospital names ship publicly.
 *
 * Each column is a `<ComplianceBadge>` plus a "Learn more" anchor that
 * jumps into the (stub) Trust Center. Anchor IDs match `/trust-center`
 * h2 IDs (`#pipa`, `#soc2`, `#iso27001`, `#hipaa`).
 */

import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";
import { ComplianceBadge, type ComplianceVariant } from "./ComplianceBadge";

const VARIANTS: ComplianceVariant[] = ["pipa", "soc2", "iso27001", "hipaa"];

export function TrustBar({ locale }: { locale: Locale }) {
  const dict = getDict(locale);
  const trustCenterBase = locale === "ko" ? "/ko/trust-center" : "/trust-center";

  return (
    <section
      data-testid="trust-bar"
      className="border-y border-border bg-bg-muted"
    >
      <div className="mx-auto max-w-content px-6 py-12">
        <div className="grid grid-cols-2 gap-6 tablet:grid-cols-4">
          {VARIANTS.map((variant) => (
            <article
              key={variant}
              aria-labelledby={`trust-${variant}-label`}
              className="flex flex-col items-start gap-3"
            >
              <ComplianceBadge variant={variant} locale={locale} />
              <span
                id={`trust-${variant}-label`}
                className="text-base font-semibold text-text"
              >
                {dict.trustBar[variant].title}
              </span>
              <span className="text-sm text-text-muted">
                {dict.trustBar[variant].status}
              </span>
              <Link
                href={`${trustCenterBase}#${variant}`}
                className="text-sm font-medium text-primary-600 hover:text-primary-700"
              >
                {dict.trustBar.learnMore} <span aria-hidden>→</span>
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
