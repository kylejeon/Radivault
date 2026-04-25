/**
 * HomepageSections — design-spec-portal-redesign §6 (vertical layout).
 *
 * Single shared component that renders sections 3..6 of the homepage:
 *   3. Value Prop 3-up           (§6.4)
 *   4. How It Works 5-step       (§6.5)
 *   5. Metrics                   (§6.6)
 *   6. Security & Compliance     (§6.7)
 *
 * Hero (§6.1/§6.2), Trust Bar (§6.3) and Footer (§6.8/§6.9) remain on
 * the page route to keep the order obvious. Splitting them keeps the
 * page file at ~30 lines and proves the locale plumbing.
 */

import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";
import { ValueTile } from "./ValueTile";
import { MetricTile } from "./MetricTile";

export function HomepageSections({ locale }: { locale: Locale }) {
  const dict = getDict(locale);

  return (
    <>
      {/* §6.4 Value Prop 3-up */}
      <section className="border-b border-border bg-bg">
        <div className="mx-auto max-w-content px-6 py-16 desktop:py-24">
          <h2 className="text-3xl font-bold text-text-strong">
            {dict.valueProp.sectionTitle}
          </h2>
          <p className="mt-3 max-w-2xl text-lg text-text-muted">
            {dict.valueProp.sectionSubtitle}
          </p>
          <div className="mt-12 grid gap-6 tablet:grid-cols-3">
            <ValueTile
              variant="icon"
              title={dict.valueProp.federated.title}
              body={dict.valueProp.federated.body}
              testId="value-tile-federated"
            />
            <ValueTile
              variant="icon"
              title={dict.valueProp.audit.title}
              body={dict.valueProp.audit.body}
              testId="value-tile-audit"
            />
            <ValueTile
              variant="icon"
              title={dict.valueProp.depth.title}
              body={dict.valueProp.depth.body}
              testId="value-tile-depth"
            />
          </div>
        </div>
      </section>

      {/* §6.5 How It Works 5-step */}
      <section className="border-b border-border bg-bg-muted">
        <div className="mx-auto max-w-content px-6 py-16 desktop:py-24">
          <h2 className="text-3xl font-bold text-text-strong">
            {dict.howItWorks.sectionTitle}
          </h2>
          <p className="mt-3 max-w-2xl text-lg text-text-muted">
            {dict.howItWorks.sectionSubtitle}
          </p>
          <ol
            className="mt-12 grid gap-4 tablet:grid-cols-3 desktop:grid-cols-5"
            data-testid="how-it-works"
          >
            {dict.howItWorks.steps.map((step, idx) => (
              <li key={step.title} className="relative">
                <ValueTile
                  variant="numbered"
                  step={idx + 1}
                  title={step.title}
                  body={step.caption}
                  testId={`step-${idx + 1}`}
                />
                {idx < dict.howItWorks.steps.length - 1 && (
                  <span
                    className="hidden text-center text-xs font-medium text-text-muted desktop:absolute desktop:right-[-12px] desktop:top-1/2 desktop:-translate-y-1/2"
                    aria-label={dict.howItWorks.arrowLabel}
                  >
                    →
                  </span>
                )}
              </li>
            ))}
          </ol>
          <div className="mt-8 text-sm text-text-muted">
            {dict.howItWorks.enginesLabel}:{" "}
            <a
              href="https://github.com/radivault/gateway-agent"
              className="text-primary-600 hover:text-primary-700"
            >
              {dict.howItWorks.gatewayLink} ↗
            </a>{" "}
            ·{" "}
            <a
              href="https://github.com/radivault/de-id-engine"
              className="text-primary-600 hover:text-primary-700"
            >
              {dict.howItWorks.deidLink} ↗
            </a>
          </div>
        </div>
      </section>

      {/* §6.6 Metrics — real-small-honest */}
      <section className="border-b border-border bg-bg">
        <div className="mx-auto max-w-content px-6 py-16 desktop:py-24">
          <h2 className="text-3xl font-bold text-text-strong">
            {dict.metrics.sectionTitle}
          </h2>
          <div
            className="mt-12 grid gap-6 tablet:grid-cols-2 desktop:grid-cols-4"
            data-testid="metrics-grid"
          >
            {dict.metrics.tiles.map((tile, i) => (
              <MetricTile
                key={i}
                value={tile.value}
                label={tile.label}
                sublabel={tile.sublabel}
                testId={`metric-tile-${i + 1}`}
              />
            ))}
          </div>
          <p
            className="mt-6 text-xs text-text-muted"
            data-testid="tcia-attribution"
          >
            {dict.metrics.tciaAttribution}
          </p>
        </div>
      </section>

      {/* §6.7 Security & Compliance */}
      <section className="bg-bg-muted">
        <div className="mx-auto max-w-content px-6 py-16 desktop:py-24">
          <h2 className="text-3xl font-bold text-text-strong">
            {dict.security.sectionTitle}
          </h2>
          <p className="mt-3 max-w-3xl text-lg text-text-muted">
            {dict.security.sectionSubtitle}
          </p>
          <div className="mt-12 grid gap-6 tablet:grid-cols-2">
            <ValueTile
              variant="icon"
              title={dict.security.pipa.title}
              body={dict.security.pipa.body}
              testId="security-pipa"
            />
            <ValueTile
              variant="icon"
              title={dict.security.network.title}
              body={dict.security.network.body}
              testId="security-network"
            />
            <ValueTile
              variant="icon"
              title={dict.security.safeHarbor.title}
              body={dict.security.safeHarbor.body}
              testId="security-safeharbor"
            />
            <ValueTile
              variant="icon"
              title={dict.security.worm.title}
              body={dict.security.worm.body}
              testId="security-worm"
            />
          </div>
          <div className="mt-8">
            <a
              href={locale === "ko" ? "/ko/trust-center" : "/trust-center"}
              className="inline-flex items-center rounded-md border border-border-strong bg-bg px-5 py-3 text-base font-medium text-text hover:bg-bg-muted"
            >
              {dict.security.cta} <span aria-hidden className="ml-2">→</span>
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
