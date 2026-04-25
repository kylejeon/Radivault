"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";

import { PasswordInput } from "@/components/auth/PasswordInput";
import { FormError } from "@/components/auth/FormError";
import { TopNav } from "@/components/TopNav";
import { getDict } from "@/lib/i18n";

function ConfirmInner() {
  const dict = getDict("en");
  const t = dict.auth.passwordReset;
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [pw1, setPw1] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pw1 !== pw2) {
      setError(t.mismatchError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/password-reset/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, newPassword: pw1 }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        if (body?.error?.code === "ERR_TOKEN_INVALID") setError(t.tokenInvalid);
        else setError(body?.error?.message ?? dict.auth.common.genericError);
        setBusy(false);
        return;
      }
      setDone(true);
      setTimeout(() => router.push("/signin"), 1500);
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <TopNav active="/password-reset" signedIn={false} />
      <main className="mx-auto max-w-md px-6 py-16">
        <h1 className="text-2xl font-semibold text-text-strong">{t.confirmTitle}</h1>
        <p className="mt-1 text-sm text-text-muted">{t.confirmSubtitle}</p>
        {done ? (
          <div className="mt-6 rounded-md border border-status-success-fg/40 bg-status-success-bg/40 p-4 text-sm text-text">
            {t.confirmDone}
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4" noValidate>
            {error ? <FormError title={error} /> : null}
            <PasswordInput
              id="reset-pw1"
              label={t.newPasswordLabel}
              required
              value={pw1}
              onChange={setPw1}
              passwordType="new"
              showStrengthMeter
              showLabel={dict.auth.common.showPassword}
              hideLabel={dict.auth.common.hidePassword}
              meterMin={dict.auth.common.passwordMeterMin}
              meterOk={dict.auth.common.passwordMeterOk}
              meterStrong={dict.auth.common.passwordMeterStrong}
              meterMax={dict.auth.common.passwordMeterMax}
            />
            <PasswordInput
              id="reset-pw2"
              label={t.confirmPasswordLabel}
              required
              value={pw2}
              onChange={setPw2}
              passwordType="new"
              showStrengthMeter={false}
              showLabel={dict.auth.common.showPassword}
              hideLabel={dict.auth.common.hidePassword}
              meterMin={dict.auth.common.passwordMeterMin}
              meterOk={dict.auth.common.passwordMeterOk}
              meterStrong={dict.auth.common.passwordMeterStrong}
              meterMax={dict.auth.common.passwordMeterMax}
            />
            <button
              type="submit"
              disabled={busy || !pw1 || !pw2 || !token}
              className="h-11 rounded-md bg-primary-600 px-4 text-base font-semibold text-white disabled:opacity-50"
            >
              {busy ? dict.auth.common.submitting : t.confirmSubmit}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}

export default function PasswordResetConfirmPage() {
  return (
    <Suspense fallback={null}>
      <ConfirmInner />
    </Suspense>
  );
}
