import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { FooterKr } from "@/components/shared/FooterKr";
import { ContactForm } from "@/components/shared/ContactForm";
import { getDict } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "문의 — RadiVault",
  description: "RadiVault 팀에 연락하세요.",
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

export default function ContactPageKr({
  searchParams,
}: {
  searchParams: { intent?: string };
}) {
  const dict = getDict("ko");
  const requested = (searchParams?.intent ?? "hospital") as IntentKey;
  const intent = VALID_INTENTS.includes(requested) ? requested : "hospital";

  return (
    <div lang="ko" className="lang-ko">
      <MarketingNav locale="ko" />
      <main id="main" className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-4xl font-bold text-text-strong">
          {dict.contact.pageTitle}
        </h1>
        <p className="mt-3 text-lg text-text-muted">
          {dict.contact.pageSubtitle}
        </p>
        <ContactForm locale="ko" defaultIntent={intent} />
      </main>
      <FooterKr />
    </div>
  );
}
