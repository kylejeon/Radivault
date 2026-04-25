"use client";

/**
 * <EmailOtpModal> — design-spec-buyer-auth §5.7 + §7 {#email-otp-modal-v1}.
 *
 * Auto-opens after signup when BUYER_AUTH_SKIP_EMAIL_VERIFY=false.
 * Focus trap + ESC + 60s resend cooldown + 10:00 TTL countdown.
 */

import { useEffect, useRef, useState } from "react";
import { OtpInput } from "./OtpInput";

export type EmailOtpModalProps = {
  open: boolean;
  email: string;
  onClose: () => void;
  onVerified: () => void;
  // i18n
  title: string;
  bodyTemplate: (email: string, mmss: string) => string;
  resendLabel: string;
  resendCooldownTemplate: (sec: number) => string;
  skipLinkLabel: string;
  legend: string;
  errorInvalidTemplate: (remaining: number) => string;
  errorExpired: string;
  errorLocked: string;
};

const TTL_MS = 10 * 60 * 1000;
const RESEND_COOLDOWN_MS = 60 * 1000;

export function EmailOtpModal({
  open,
  email,
  onClose,
  onVerified,
  title,
  bodyTemplate,
  resendLabel,
  resendCooldownTemplate,
  skipLinkLabel,
  legend,
  errorInvalidTemplate,
  errorExpired,
  errorLocked,
}: EmailOtpModalProps) {
  const [remaining, setRemaining] = useState(TTL_MS);
  const [resendCooldown, setResendCooldown] = useState(RESEND_COOLDOWN_MS);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  // TTL ticker
  useEffect(() => {
    if (!open) return;
    setRemaining(TTL_MS);
    const t = setInterval(() => setRemaining((r) => Math.max(0, r - 1000)), 1000);
    return () => clearInterval(t);
  }, [open]);

  // Resend cooldown ticker
  useEffect(() => {
    if (!open) return;
    setResendCooldown(RESEND_COOLDOWN_MS);
    const t = setInterval(
      () => setResendCooldown((r) => Math.max(0, r - 1000)),
      1000,
    );
    return () => clearInterval(t);
  }, [open]);

  // ESC handler + focus trap baseline
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const mm = String(Math.floor(remaining / 60_000)).padStart(2, "0");
  const ss = String(Math.floor((remaining % 60_000) / 1000)).padStart(2, "0");

  async function submit(code: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, otp: code }),
      });
      if (res.ok) {
        onVerified();
        return;
      }
      const body = await res.json().catch(() => ({}));
      const errCode = body?.error?.code as string | undefined;
      if (errCode === "ERR_OTP_EXPIRED") setError(errorExpired);
      else if (errCode === "ERR_OTP_LOCKED") setError(errorLocked);
      else if (errCode === "ERR_OTP_INVALID") {
        const m = String(body?.error?.message ?? "").match(/(\d+) attempt/);
        const remainingAttempts = m ? Number(m[1]) : 0;
        setError(errorInvalidTemplate(remainingAttempts));
      } else {
        setError(body?.error?.message ?? "Verification failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setBusy(true);
    try {
      await fetch("/api/auth/resend-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setResendCooldown(RESEND_COOLDOWN_MS);
      setError(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="otp-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-text/40 p-4"
    >
      <div
        ref={dialogRef}
        className="w-full max-w-md rounded-md bg-bg p-6 shadow-overlay sm:max-w-md"
        // mobile bottom-sheet via CSS — Kyle Q3 default
      >
        <div className="flex items-start justify-between">
          <h2 id="otp-modal-title" className="text-base font-semibold text-text">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-text-muted hover:bg-bg-muted"
          >
            ×
          </button>
        </div>
        <p className="mt-2 text-sm text-text-muted">
          {bodyTemplate(email, `${mm}:${ss}`)}
        </p>
        <div className="mt-4">
          <OtpInput
            legend={legend}
            autoFocus
            error={Boolean(error)}
            errorMessage={error}
            disabled={busy || remaining === 0}
            onComplete={submit}
          />
        </div>
        <hr className="my-4 border-border" />
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={resend}
            disabled={busy || resendCooldown > 0}
            className="text-sm font-medium text-primary-700 disabled:text-text-muted"
          >
            {resendCooldown > 0
              ? resendCooldownTemplate(Math.ceil(resendCooldown / 1000))
              : resendLabel}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-text-muted underline"
          >
            {skipLinkLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
