import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { FooterEn } from "@/components/shared/FooterEn";
import { ComplianceBadge } from "@/components/shared/ComplianceBadge";
import { getDict } from "@/lib/i18n";

/**
 * Trust Center stub. v0.1 — surfaces the four compliance badges and
 * anchors that the homepage Trust Bar links into. Full control
 * documentation is Kyle decision K-3 and lands once SOC 2 audit window
 * opens.
 */

export const metadata: Metadata = {
  title: "Trust Center — RadiVault",
  description: "RadiVault compliance posture and operational controls.",
  robots: { index: true, follow: true },
};

export default function TrustCenterPage() {
  const dict = getDict("en");
  return (
    <>
      <MarketingNav locale="en" />
      <main id="main" className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-4xl font-bold text-text-strong">
          {dict.trustCenter.pageTitle}
        </h1>
        <p className="mt-3 text-lg text-text-muted">
          {dict.trustCenter.pageSubtitle}
        </p>
        <p className="mt-6 rounded-md border border-border bg-bg-muted p-4 text-sm text-text-muted">
          {dict.trustCenter.comingSoon}
        </p>
        <div className="mt-12 space-y-12">
          {(["pipa", "soc2", "iso27001", "hipaa"] as const).map((variant) => (
            <section key={variant} id={variant} className="scroll-mt-20">
              <ComplianceBadge variant={variant} locale="en" />
              <h2 className="mt-3 text-2xl font-semibold text-text">
                {dict.trustBar[variant].title}
              </h2>
              <p className="mt-2 text-base text-text-muted">
                {dict.trustBar[variant].status}.
              </p>
            </section>
          ))}
        </div>
      </main>
      <FooterEn />
    </>
  );
}
