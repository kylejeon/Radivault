"use client";

import { useState } from "react";

import { TextInput } from "@/components/auth/TextInput";
import { FormError } from "@/components/auth/FormError";
import { TopNav } from "@/components/TopNav";
import { getDict } from "@/lib/i18n";

/**
 * /password-reset — request a reset link (FR-AUTH-6 step 1).
 *
 * Always reports success-style "check your email" message; the BFF returns
 * 200 regardless of whether the email exists (no enumeration leak).
 */
export default function PasswordResetRequestPage() {
  const dict = getDict("en");
  const t = dict.auth.passwordReset;

  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/password-reset/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        if (body?.error?.code === "ERR_RATE_LIMITED") {
          setError(dict.auth.errors.rateLimited);
        } else {
          setError(body?.error?.message ?? dict.auth.common.genericError);
        }
        setBusy(false);
        return;
      }
      setSubmitted(true);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <TopNav active="/password-reset" signedIn={false} />
      <main className="mx-auto max-w-md px-6 py-16">
        <h1 className="text-2xl font-semibold text-text-strong">{t.requestTitle}</h1>
        <p className="mt-1 text-sm text-text-muted">{t.requestSubtitle}</p>
        {submitted ? (
          <div className="mt-6 rounded-md border border-status-success-fg/40 bg-status-success-bg/40 p-4 text-sm text-text">
            {t.requestDone}
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4" noValidate>
            {error ? <FormError title={error} /> : null}
            <TextInput
              id="reset-email"
              label={dict.auth.signin.fields.email}
              type="email"
              required
              value={email}
              onChange={setEmail}
              autoComplete="email"
            />
            <button
              type="submit"
              disabled={busy || !email}
              className="h-11 rounded-md bg-primary-600 px-4 text-base font-semibold text-white disabled:opacity-50"
            >
              {busy ? dict.auth.common.submitting : t.requestSubmit}
            </button>
          </form>
        )}
        <p className="mt-4 text-sm">
          <a href="/signin" className="text-primary-700 underline">
            {t.backToSignin}
          </a>
        </p>
      </main>
    </div>
  );
}
