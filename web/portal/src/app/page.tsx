import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { Hero } from "@/components/shared/Hero";
import { TrustBar } from "@/components/shared/TrustBar";
import { HomepageSections } from "@/components/shared/HomepageSections";
import { FooterEn } from "@/components/shared/FooterEn";
import { getDict } from "@/lib/i18n";

/**
 * EN homepage (`/`) — design-spec-portal-redesign §6 (sections 1..7).
 *
 * Public, unauthenticated. The post-sign-in dashboard is `web/portal/src/
 * app/(authed)/page.tsx` (delivered in Phase 3). The buyer / hospital
 * portals (`/search`, `/orders`, `/hospital/*`) remain reachable via
 * the existing signin flow and are not touched here.
 *
 * Static-friendly: no session reads, no upstream calls. Next.js will
 * happily prerender this at build time when the server bundle is
 * produced.
 */
export const metadata: Metadata = (() => {
  const dict = getDict("en");
  return {
    title: dict.meta.title,
    description: dict.meta.description,
    alternates: {
      canonical: "https://radivault.io/",
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
      url: "https://radivault.io/",
    },
    twitter: {
      card: "summary_large_image",
      title: dict.meta.title,
      description: dict.meta.description,
    },
    // Public marketing — let crawlers in.
    robots: { index: true, follow: true },
  };
})();

export default function HomePage() {
  return (
    <>
      <OrganizationJsonLd />
      <MarketingNav locale="en" />
      <main id="main">
        <Hero locale="en" />
        <TrustBar locale="en" />
        <HomepageSections locale="en" />
      </main>
      <FooterEn />
    </>
  );
}

function OrganizationJsonLd() {
  const data = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "RadiVault Inc.",
    url: "https://radivault.io/",
    description:
      "RadiVault delivers anonymized Korean medical imaging data to global AI teams under PIPA §28-8.",
    sameAs: ["https://github.com/radivault"],
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
