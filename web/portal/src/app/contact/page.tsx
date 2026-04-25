import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { FooterEn } from "@/components/shared/FooterEn";
import { ContactForm } from "@/components/shared/ContactForm";
import { getDict } from "@/lib/i18n";

/**
 * Contact (FR-HP-12). Real submit relay shipped — POSTs to /api/contact
 * (HIGH-1 fix from qa-report-portal-redesign).
 */

export const metadata: Metadata = {
  title: "Contact — RadiVault",
  description: "Reach the RadiVault team.",
  robots: { index: true, follow: true },
};

type IntentKey = "buyer" | "hospital" | "press" | "investor" | "other";

const VALID_INTENTS: IntentKey[] = [
  "buyer",
  "hospital",
  "press",
  "investor",
  "other",
];

export default function ContactPage({
  searchParams,
}: {
  searchParams: { intent?: string };
}) {
  const dict = getDict("en");
  const requested = (searchParams?.intent ?? "buyer") as IntentKey;
  const intent = VALID_INTENTS.includes(requested) ? requested : "buyer";

  return (
    <>
      <MarketingNav locale="en" />
      <main id="main" className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-4xl font-bold text-text-strong">
          {dict.contact.pageTitle}
        </h1>
        <p className="mt-3 text-lg text-text-muted">
          {dict.contact.pageSubtitle}
        </p>
        <ContactForm locale="en" defaultIntent={intent} />
      </main>
      <FooterEn />
    </>
  );
}
