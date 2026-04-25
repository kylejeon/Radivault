import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { FooterKr } from "@/components/shared/FooterKr";
import { ComplianceBadge } from "@/components/shared/ComplianceBadge";
import { getDict } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Trust Center — RadiVault",
  description: "RadiVault 컴플라이언스 자세 및 운영 컨트롤.",
  robots: { index: true, follow: true },
};

export default function TrustCenterPageKr() {
  const dict = getDict("ko");
  return (
    <div lang="ko" className="lang-ko">
      <MarketingNav locale="ko" />
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
              <ComplianceBadge variant={variant} locale="ko" />
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
      <FooterKr />
    </div>
  );
}
