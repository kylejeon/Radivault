import type { Metadata } from "next";
import { MarketingNav } from "@/components/shared/MarketingNav";
import { FooterKr } from "@/components/shared/FooterKr";
import { getDict } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "문의 — RadiVault",
  description: "RadiVault 팀에 연락하세요.",
  robots: { index: true, follow: true },
};

export default function ContactPageKr({
  searchParams,
}: {
  searchParams: { intent?: string };
}) {
  const dict = getDict("ko");
  const intent = (searchParams?.intent ?? "hospital") as keyof typeof dict.contact.intents;

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
        <form className="mt-10 space-y-6" data-testid="contact-form-ko">
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
              className="w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:border-teal-600 focus:outline-none"
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
              className="w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:border-teal-600 focus:outline-none"
            />
          </label>
          <button
            type="button"
            className="inline-flex items-center rounded-md bg-teal-600 px-5 py-3 text-base font-medium text-white hover:bg-teal-700"
            disabled
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
      <FooterKr />
    </div>
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
        className="w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:border-teal-600 focus:outline-none"
      />
    </label>
  );
}
