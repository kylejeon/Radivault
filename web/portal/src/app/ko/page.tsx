import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { Hero } from "@/components/shared/Hero";
import { TrustBar } from "@/components/shared/TrustBar";
import { HomepageSections } from "@/components/shared/HomepageSections";
import { FooterKr } from "@/components/shared/FooterKr";
import { getDict } from "@/lib/i18n";

/**
 * KR homepage (`/ko`) — design-spec-portal-redesign §6.2 + §6.9.
 *
 * Structurally mirrors `/` but renders the Korean dict and the KR
 * footer (with the §5.8 legal block enforced by FR-HP-9).
 */
export const metadata: Metadata = (() => {
  const dict = getDict("ko");
  return {
    title: dict.meta.title,
    description: dict.meta.description,
    alternates: {
      canonical: "https://radivault.io/ko",
      languages: {
        en: "https://radivault.io/",
        ko: "https://radivault.io/ko",
        "x-default": "https://radivault.io/",
      },
    },
    openGraph: {
      type: "website",
      title: dict.meta.title,
      description: dict.meta.description,
      url: "https://radivault.io/ko",
      locale: "ko_KR",
    },
    twitter: {
      card: "summary_large_image",
      title: dict.meta.title,
      description: dict.meta.description,
    },
    robots: { index: true, follow: true },
  };
})();

export default function HomePageKr() {
  return (
    <div lang="ko" className="lang-ko">
      <MarketingNav locale="ko" />
      <main id="main">
        <Hero locale="ko" />
        <TrustBar locale="ko" />
        <HomepageSections locale="ko" />
      </main>
      <FooterKr />
    </div>
  );
}
