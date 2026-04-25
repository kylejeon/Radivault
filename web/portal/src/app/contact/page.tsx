import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { FooterEn } from "@/components/shared/FooterEn";
import { getDict } from "@/lib/i18n";

/**
 * Contact stub (FR-HP-12). v0.1 — read-only form skeleton with mailto
 * fallback. The POST /api/contact relay arrives in FR-INF-4 (Phase 3 / 4).
 */

export const metadata: Metadata = {
  title: "Contact — RadiVault",
  description: "Reach the RadiVault team.",
  robots: { index: true, follow: true },
};

export default function ContactPage({
  searchParams,
}: {
  searchParams: { intent?: string };
}) {
  const dict = getDict("en");
  const intent = (searchParams?.intent ?? "buyer") as keyof typeof dict.contact.intents;

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
        <form className="mt-10 space-y-6" data-testid="contact-form">
          <Field label={dict.contact.fields.name} name="name" />
          <Field label={dict.contact.fields.company} name="company" />
          <Field label={dict.contact.fields.email} name="email" type="email" />
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-text">
              {dict.contact.fields.intent}
            </span>
            <select
              name="intent"
              defaultValue={intent}
              className="w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:border-primary-600 focus:outline-none"
            >
              {(Object.keys(dict.contact.intents) as Array<
                keyof typeof dict.contact.intents
              >).map((key) => (
                <option key={key} value={key}>
                  {dict.contact.intents[key]}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-text">
              {dict.contact.fields.message}
            </span>
            <textarea
              name="message"
              rows={5}
              className="w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:border-primary-600 focus:outline-none"
            />
          </label>
          <button
            type="button"
            className="inline-flex items-center rounded-md bg-primary-600 px-5 py-3 text-base font-medium text-white hover:bg-primary-700"
            disabled
            data-testid="contact-submit"
          >
            {dict.contact.submit}
          </button>
          <p className="text-sm text-text-muted">
            {dict.contact.successPlaceholder}
          </p>
          <p className="text-sm text-text-muted">
            {dict.contact.mailtoFallback}:{" "}
            <a
              className="text-primary-600 hover:text-primary-700"
              href="mailto:sales@radivault.io"
            >
              sales@radivault.io
            </a>
          </p>
        </form>
      </main>
      <FooterEn />
    </>
  );
}

function Field({
  label,
  name,
  type = "text",
}: {
  label: string;
  name: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-text">{label}</span>
      <input
        type={type}
        name={name}
        className="w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:border-primary-600 focus:outline-none"
      />
    </label>
  );
}
