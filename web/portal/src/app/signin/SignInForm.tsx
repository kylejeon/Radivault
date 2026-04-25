"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { TextInput } from "@/components/auth/TextInput";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { FormError } from "@/components/auth/FormError";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getDict, type Locale } from "@/lib/i18n";

/**
 * <SignInForm> — design-spec-buyer-auth §6 wireframe.
 *
 * v0.2: email + password is the primary path. The legacy 50-char API key
 * paste mode is hidden behind an "advanced" toggle (90-day deprecation
 * window per dev-spec §12.2).
 */
export function SignInForm({ locale }: { locale: Locale }) {
  const router = useRouter();
  const dict = getDict(locale);
  const t = dict.auth;

  const [mode, setMode] = useState<"email" | "legacy">("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [legacyKey, setLegacyKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [topError, setTopError] = useState<{
    title: string;
    hint?: string;
    requestId?: string;
    action?: { label: string; href: string };
  } | null>(null);
  const [legacyError, setLegacyError] = useState<{
    code?: string;
    detail?: string;
    requestId?: string;
  } | null>(null);

  async function onSubmitEmail(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setTopError(null);
    try {
      const res = await fetch("/api/auth/signin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, rememberMe: true }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const code = body?.error?.code as string | undefined;
        const requestId = body?.request_id as string | undefined;
        if (code === "ERR_AUTH_INVALID") {
          setTopError({ title: t.errors.authInvalid, requestId });
        } else if (code === "ERR_RATE_LIMITED") {
          setTopError({ title: t.errors.rateLimited, requestId });
        } else if (code === "ERR_ACCOUNT_LOCKED") {
          setTopError({
            title: t.errors.accountLocked,
            action: {
              label: t.signin.forgotPassword,
              href: "/password-reset",
            },
            requestId,
          });
        } else {
          setTopError({
            title: body?.error?.message ?? t.common.genericError,
            requestId,
          });
        }
        setSubmitting(false);
        // clear password but keep email
        setPassword("");
        return;
      }
      router.push("/search");
    } catch (err) {
      setTopError({ title: t.common.genericError, hint: String(err) });
      setSubmitting(false);
    }
  }

  async function onSubmitLegacy(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setLegacyError(null);
    try {
      const res = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: legacyKey }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setLegacyError({
          code: body?.error ?? "ERR_AUTH_INVALID",
          detail: body?.detail,
          requestId: body?.request_id,
        });
        setSubmitting(false);
        return;
      }
      router.push("/search");
    } catch (err) {
      setLegacyError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {mode === "email" ? (
        <form onSubmit={onSubmitEmail} className="flex flex-col gap-4" data-testid="signin-form-email" noValidate>
          {topError ? (
            <FormError
              title={topError.title}
              hint={topError.hint}
              action={topError.action}
              requestId={topError.requestId}
            />
          ) : null}
          <TextInput
            id="signin-email"
            label={t.signin.fields.email}
            type="email"
            required
            value={email}
            onChange={setEmail}
            autoComplete="email"
            requiredLabel={t.common.requiredLabel}
          />
          <PasswordInput
            id="signin-password"
            label={t.signin.fields.password}
            required
            value={password}
            onChange={setPassword}
            showStrengthMeter={false}
            passwordType="current"
            requiredLabel={t.common.requiredLabel}
            showLabel={t.common.showPassword}
            hideLabel={t.common.hidePassword}
            meterMin={t.common.passwordMeterMin}
            meterOk={t.common.passwordMeterOk}
            meterStrong={t.common.passwordMeterStrong}
            meterMax={t.common.passwordMeterMax}
          />
          <div className="flex items-center justify-between text-sm">
            <a href="/password-reset" className="text-primary-700 underline">
              {t.signin.forgotPassword}
            </a>
          </div>
          <button
            type="submit"
            disabled={submitting || !email || !password}
            data-testid="signin-submit"
            className="h-11 rounded-md bg-primary-600 px-4 text-base font-semibold text-white disabled:opacity-50"
          >
            {submitting ? t.common.submitting : t.signin.submitCta}
          </button>
        </form>
      ) : (
        <form onSubmit={onSubmitLegacy} className="flex flex-col gap-4" data-testid="signin-form-legacy" noValidate>
          <p className="text-xs text-text-muted">{t.signin.legacyHelper}</p>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-text">{t.signin.legacyKeyLabel}</span>
            <input
              type="password"
              value={legacyKey}
              onChange={(e) => setLegacyKey(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder="rv_live_…"
              required
              className="h-11 rounded-md border border-border-strong bg-bg px-3 font-mono text-sm focus:border-primary-600 focus:outline-none"
            />
          </label>
          {legacyError ? (
            <ErrorBanner
              code={legacyError.code}
              requestId={legacyError.requestId}
              detail={legacyError.detail}
            />
          ) : null}
          <button
            type="submit"
            disabled={submitting || !legacyKey}
            className="h-11 rounded-md bg-primary-600 px-4 text-base font-semibold text-white disabled:opacity-50"
          >
            {submitting ? t.common.submitting : t.signin.submitCta}
          </button>
        </form>
      )}

      <div className="flex items-center justify-between border-t border-border pt-4 text-sm">
        <button
          type="button"
          onClick={() => setMode((m) => (m === "email" ? "legacy" : "email"))}
          data-testid="signin-toggle-mode"
          className="text-text-muted underline"
        >
          {mode === "email" ? t.signin.legacyToggle : "← Email + password"}
        </button>
        <span className="text-text-muted">
          {t.signin.altSignup}{" "}
          <a
            href={locale === "ko" ? "/ko/signup" : "/signup"}
            className="font-medium text-primary-700 underline"
          >
            {t.signin.altSignupLink}
          </a>
        </span>
      </div>
    </div>
  );
}
