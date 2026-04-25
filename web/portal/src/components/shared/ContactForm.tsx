"use client";

/**
 * ContactForm — HIGH-1 + MEDIUM-7 fix from qa-report-portal-redesign.
 *
 * Posts to /api/contact (FR-INF-5). Includes the PIPA L-7 consent
 * checkbox + retention disclosure. EN and KR pages share this client
 * island; locale flips both the labels (i18n) and the accent colour
 * (Buyer blue vs Hospital teal — design-spec §5.1/5.2).
 */

import { useState } from "react";
import { getDict, type Locale } from "@/lib/i18n";

type IntentKey = "buyer" | "hospital" | "press" | "investor" | "other";

export function ContactForm({
  locale = "en",
  defaultIntent = "buyer",
}: {
  locale?: Locale;
  defaultIntent?: IntentKey;
}) {
  const dict = getDict(locale);
  const accent = locale === "ko" ? "teal" : "primary";
  const focusBorder =
    accent === "teal" ? "focus:border-teal-600" : "focus:border-primary-600";
  const buttonBase =
    accent === "teal"
      ? "bg-teal-600 hover:bg-teal-700"
      : "bg-primary-600 hover:bg-primary-700";

  const [name, setName] = useState("");
  const [organization, setOrganization] = useState("");
  const [email, setEmail] = useState("");
  const [intent, setIntent] = useState<IntentKey>(defaultIntent);
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<"idle" | "submitting" | "ok" | "error">(
    "idle",
  );
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  const canSubmit =
    consent &&
    name.trim().length > 0 &&
    email.trim().length > 0 &&
    message.trim().length >= 10 &&
    status !== "submitting";

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit) return;
    setStatus("submitting");
    setErrorDetail(null);
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          organization: organization.trim(),
          intent,
          message: message.trim(),
          consent: true,
        }),
      });
      if (res.status === 202) {
        setStatus("ok");
        setName("");
        setOrganization("");
        setMessage("");
        setConsent(false);
        return;
      }
      let body: { error?: string; message?: string } = {};
      try {
        body = (await res.json()) as { error?: string; message?: string };
      } catch {
        /* swallow */
      }
      setStatus("error");
      setErrorDetail(body.message ?? body.error ?? null);
    } catch {
      setStatus("error");
      setErrorDetail(null);
    }
  }

  return (
    <form
      className="mt-10 space-y-6"
      data-testid={locale === "ko" ? "contact-form-ko" : "contact-form"}
      onSubmit={handleSubmit}
    >
      <Field
        label={dict.contact.fields.name}
        name="name"
        value={name}
        onChange={setName}
        focusBorder={focusBorder}
      />
      <Field
        label={dict.contact.fields.company}
        name="organization"
        value={organization}
        onChange={setOrganization}
        focusBorder={focusBorder}
      />
      <Field
        label={dict.contact.fields.email}
        name="email"
        type="email"
        value={email}
        onChange={setEmail}
        focusBorder={focusBorder}
      />

      <label className="block">
        <span className="mb-1 block text-sm font-medium text-text">
          {dict.contact.fields.intent}
        </span>
        <select
          name="intent"
          value={intent}
          onChange={(e) => setIntent(e.target.value as IntentKey)}
          className={`w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:outline-none ${focusBorder}`}
        >
          {(Object.keys(dict.contact.intents) as IntentKey[]).map((key) => (
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
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className={`w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:outline-none ${focusBorder}`}
        />
      </label>

      {/* PIPA L-7 consent — MEDIUM-7. */}
      <label
        className="flex items-start gap-2 rounded-md border border-border bg-bg-muted p-3 text-sm text-text"
        data-testid="contact-consent"
      >
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5 size-4"
          data-testid="contact-consent-checkbox"
          required
        />
        <span>{dict.contact.consentLabel}</span>
      </label>
      {!consent ? (
        <p className="text-xs text-text-muted">
          {dict.contact.consentRequiredHint}
        </p>
      ) : null}

      <button
        type="submit"
        data-testid="contact-submit"
        disabled={!canSubmit}
        className={`inline-flex items-center rounded-md px-5 py-3 text-base font-medium text-white disabled:opacity-50 ${buttonBase}`}
      >
        {status === "submitting"
          ? dict.contact.submitting
          : dict.contact.submit}
      </button>

      {status === "ok" ? (
        <p
          className="text-sm text-status-success-fg"
          role="status"
          data-testid="contact-success"
        >
          {dict.contact.successPlaceholder}
        </p>
      ) : null}
      {status === "error" ? (
        <p
          className="text-sm text-status-error-fg"
          role="alert"
          data-testid="contact-error"
        >
          {errorDetail ?? dict.contact.submitError}
        </p>
      ) : null}

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
  );
}

function Field({
  label,
  name,
  value,
  onChange,
  type = "text",
  focusBorder,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  focusBorder: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-text">{label}</span>
      <input
        type={type}
        name={name}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full rounded-md border border-border-strong bg-bg px-3 py-2 text-base text-text focus:outline-none ${focusBorder}`}
      />
    </label>
  );
}
