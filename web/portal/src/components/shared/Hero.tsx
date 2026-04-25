/**
 * Hero — design-spec-portal-redesign §5.1 ({#hero-en-v1}) and §5.2 ({#hero-kr-v1}).
 *
 * Two-column layout: text on the left, screenshot frame on the right.
 * Mobile collapses to one column with the screenshot below the headline
 * (per §7.1).
 *
 * The right-side "screenshot" placeholder is rendered as a styled mock
 * panel rather than a real image. Replacing it with the canonical
 * `/search` capture is Kyle decision K-2 and tracked in §10 of the
 * design-spec; substituting the image only requires swapping the
 * <HeroScreenshotMock> body — no API changes.
 */

import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";
import { CtaPair } from "./CtaPair";

export function Hero({ locale }: { locale: Locale }) {
  const dict = getDict(locale);
  const accent: "blue" | "teal" = locale === "ko" ? "teal" : "blue";
  const eyebrowColor =
    locale === "ko" ? "text-teal-600" : "text-primary-600";

  return (
    <section
      data-testid={`hero-${locale}`}
      className="border-b border-border bg-gradient-to-b from-primary-50/40 to-bg"
    >
      <div className="mx-auto grid max-w-content gap-12 px-6 py-16 desktop:grid-cols-2 desktop:gap-16 desktop:py-24">
        <div className="flex flex-col items-start gap-6">
          <span className={`text-sm font-medium ${eyebrowColor}`}>
            {dict.hero.eyebrow}
          </span>
          <h1
            data-testid="hero-headline"
            className="text-5xl font-bold tracking-tight text-text-strong desktop:text-6xl"
          >
            {dict.hero.headline}
          </h1>
          <p className="max-w-xl text-lg text-text-muted">
            {dict.hero.subhead}
          </p>
          <CtaPair
            primaryLabel={dict.hero.primaryCta}
            primaryHref={
              locale === "ko"
                ? "/ko/contact?intent=hospital"
                : "/contact?intent=buyer"
            }
            secondaryLabel={dict.hero.secondaryCta}
            secondaryHref={locale === "ko" ? "/docs" : "/docs"}
            accent={accent}
            primaryTestId="hero-cta-primary"
            secondaryTestId="hero-cta-secondary"
          />
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-text-muted">
            <Link
              href={
                locale === "ko"
                  ? "/ko/contact?intent=investor"
                  : "/contact?intent=investor"
              }
              className="hover:text-text"
            >
              {dict.hero.forInvestors} <span aria-hidden>→</span>
            </Link>
            <Link
              href={
                locale === "ko"
                  ? "/ko/contact?intent=press"
                  : "/contact?intent=hospital"
              }
              className="hover:text-text"
            >
              {dict.hero.forHospitals} <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <HeroScreenshotMock alt={dict.hero.screenshotAlt} locale={locale} />
          <p className="text-xs text-text-muted">
            {dict.hero.screenshotCaption}
          </p>
        </div>
      </div>
    </section>
  );
}

/**
 * Placeholder for the canonical `/search` 3-pane screenshot. The real image
 * lands once Kyle approves K-2 (resolution + facet seed). Until then this
 * static mock conveys the same layout signals (facet pane / results table /
 * cohort sidebar) without exposing any pilot hospital names.
 */
function HeroScreenshotMock({
  alt,
  locale,
}: {
  alt: string;
  locale: Locale;
}) {
  const labels =
    locale === "ko"
      ? {
          facets: "패싯",
          results: "결과 테이블",
          cohort: "코호트",
          fromHospitals: "2 병원에서",
        }
      : {
          facets: "Facets",
          results: "Results",
          cohort: "Cohort",
          fromHospitals: "From 2 hospitals",
        };

  return (
    <div
      role="img"
      aria-label={alt}
      data-testid="hero-screenshot"
      className="overflow-hidden rounded-lg border border-border bg-bg shadow-hero"
    >
      <div className="flex items-center gap-1 border-b border-border bg-bg-muted px-3 py-2">
        <span className="size-2 rounded-pill bg-status-error-fg/60" aria-hidden />
        <span className="size-2 rounded-pill bg-status-warning-fg/60" aria-hidden />
        <span className="size-2 rounded-pill bg-status-success-fg/60" aria-hidden />
        <span className="ml-3 truncate text-xs text-text-muted">
          portal.radivault.io/search
        </span>
      </div>
      <div className="grid h-72 grid-cols-[140px_1fr_140px] gap-2 p-3">
        <div className="rounded-md bg-bg-muted p-2">
          <div className="mb-2 text-xs font-semibold text-text">
            {labels.facets}
          </div>
          <div className="space-y-1">
            {["modality", "body_part", "age", "sex", "manufacturer"].map(
              (key) => (
                <div key={key} className="h-3 w-full rounded bg-border" />
              ),
            )}
          </div>
        </div>
        <div className="rounded-md border border-border p-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-text">
              {labels.results}
            </span>
            <span className="rounded-pill bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700">
              {labels.fromHospitals}
            </span>
          </div>
          <div className="space-y-1">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center gap-1">
                <div className="size-3 rounded bg-border" />
                <div
                  className="h-3 rounded"
                  style={{
                    width: `${30 + ((i * 13) % 50)}%`,
                    background:
                      i % 3 === 0
                        ? "#dbeafe"
                        : i % 3 === 1
                          ? "#ede9fe"
                          : "#dcfce7",
                  }}
                />
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-md bg-bg-muted p-2">
          <div className="mb-2 text-xs font-semibold text-text">
            {labels.cohort}
          </div>
          <div className="space-y-1">
            <div className="h-3 w-2/3 rounded bg-border" />
            <div className="h-3 w-1/2 rounded bg-border" />
            <div className="h-3 w-3/4 rounded bg-border" />
          </div>
        </div>
      </div>
    </div>
  );
}
