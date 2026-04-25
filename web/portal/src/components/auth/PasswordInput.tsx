"use client";

/**
 * <PasswordInput> — design-spec-buyer-auth §5.2 {#password-input-v1}.
 *
 * Password field with show/hide toggle + length meter (NIST SP 800-63B
 * Rev.4: length-only). Toggle auto-rehides after 30s.
 */

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

export type PasswordInputProps = {
  id: string;
  label: string;
  required?: boolean;
  helper?: string;
  error?: string | null;
  value: string;
  onChange: (next: string) => void;
  showStrengthMeter?: boolean;
  passwordType?: "new" | "current";
  // i18n
  requiredLabel?: string;
  showLabel?: string;
  hideLabel?: string;
  meterMin?: string; // "Minimum 8 characters."
  meterOk?: string; // "OK. Longer is better."
  meterStrong?: string; // "Strong length."
  meterMax?: string; // "Maximum 64 characters."
  meterCountFormat?: (current: number, max: number) => string; // "9 / 64 characters"
  disabled?: boolean;
};

const HIDE_AFTER_MS = 30_000;
const MAX = 64;

export function PasswordInput({
  id,
  label,
  required = false,
  helper,
  error,
  value,
  onChange,
  showStrengthMeter = true,
  passwordType = "new",
  requiredLabel = "* required",
  showLabel = "Show password",
  hideLabel = "Hide password",
  meterMin = "Minimum 8 characters.",
  meterOk = "OK. Longer is better.",
  meterStrong = "Strong length.",
  meterMax = "Maximum 64 characters.",
  meterCountFormat = (c, m) => `${c} / ${m} characters`,
  disabled = false,
}: PasswordInputProps) {
  const [reveal, setReveal] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!reveal) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setReveal(false), HIDE_AFTER_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [reveal, value]);

  const errorId = error ? `${id}-error` : undefined;
  const helperId = helper && !error ? `${id}-helper` : undefined;
  const meterId = showStrengthMeter ? `${id}-meter` : undefined;

  const length = value.length;
  let meterColor = "bg-status-error-fg";
  let meterMessage = meterMin;
  if (length === 0) {
    meterColor = "bg-border";
    meterMessage = meterMin;
  } else if (length < 8) {
    meterColor = "bg-status-error-fg";
    meterMessage = meterMin;
  } else if (length < 12) {
    meterColor = "bg-status-warning-fg";
    meterMessage = meterOk;
  } else if (length <= MAX) {
    meterColor = "bg-status-success-fg";
    meterMessage = meterStrong;
  } else {
    meterColor = "bg-status-error-fg";
    meterMessage = meterMax;
  }
  const meterFillPct = Math.min(100, Math.round((length / MAX) * 100));

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className="flex items-center justify-between text-sm font-medium text-text"
      >
        <span>{label}</span>
        {required ? (
          <span className="text-xs font-normal text-text-muted">{requiredLabel}</span>
        ) : null}
      </label>
      <div className="relative">
        <input
          id={id}
          type={reveal ? "text" : "password"}
          required={required}
          aria-required={required || undefined}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={[errorId, helperId, meterId].filter(Boolean).join(" ") || undefined}
          autoComplete={passwordType === "new" ? "new-password" : "current-password"}
          maxLength={MAX + 1 /* allow detecting >MAX for the lint-out message */}
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, MAX))}
          disabled={disabled}
          className={clsx(
            "h-11 w-full rounded-md border bg-bg pl-4 pr-12 text-base text-text",
            "outline-none transition-colors font-mono",
            error
              ? "border-2 border-status-error-fg focus:border-status-error-fg focus:ring-2 focus:ring-status-error-fg/30"
              : "border-border-strong hover:border-text-muted focus:border-primary-600 focus:ring-2 focus:ring-primary-600/30",
            disabled && "cursor-not-allowed bg-bg-muted opacity-60",
          )}
        />
        <button
          type="button"
          onClick={() => setReveal((r) => !r)}
          aria-label={reveal ? hideLabel : showLabel}
          aria-pressed={reveal}
          className="absolute right-2 top-1/2 z-10 -translate-y-1/2 rounded p-2 text-text-muted hover:bg-bg-muted focus:outline-none focus:ring-2 focus:ring-primary-600/40"
        >
          {reveal ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
              aria-hidden
            >
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
              <line x1="1" y1="1" x2="23" y2="23" />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
              aria-hidden
            >
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          )}
        </button>
      </div>
      {error ? (
        <p
          id={errorId}
          role="alert"
          aria-live="polite"
          className="flex items-center gap-1 text-xs text-status-error-fg"
        >
          <span aria-hidden>⚠</span> {error}
        </p>
      ) : helper ? (
        <p id={helperId} className="text-xs text-text-muted">
          {helper}
        </p>
      ) : null}
      {showStrengthMeter ? (
        <div id={meterId} className="mt-1 flex items-center gap-2">
          <div className="h-1.5 flex-1 rounded-pill bg-border-strong/40">
            <div
              className={clsx("h-full rounded-pill transition-all", meterColor)}
              style={{ width: `${meterFillPct}%` }}
              aria-hidden
            />
          </div>
          <span className="text-xs text-text-muted">
            {meterCountFormat(length, MAX)}
          </span>
        </div>
      ) : null}
      {showStrengthMeter && length > 0 ? (
        <p className="text-xs text-text-muted">{meterMessage}</p>
      ) : null}
    </div>
  );
}
