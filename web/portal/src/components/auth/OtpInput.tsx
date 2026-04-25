"use client";

/**
 * <OtpInput> — design-spec-buyer-auth §5.3 {#otp-input-v1}.
 *
 * 6 digit boxes with auto-advance, paste-distribution, and shake-on-error
 * (respects prefers-reduced-motion).
 */

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

export type OtpInputProps = {
  length?: number;
  legend: string;
  error?: boolean;
  errorMessage?: string | null;
  autoFocus?: boolean;
  onComplete?: (code: string) => void;
  onChange?: (code: string) => void;
  disabled?: boolean;
  // i18n
  digitLabel?: (i: number, total: number) => string;
};

export function OtpInput({
  length = 6,
  legend,
  error = false,
  errorMessage,
  autoFocus = false,
  onComplete,
  onChange,
  disabled = false,
  digitLabel = (i, total) => `Digit ${i + 1} of ${total}`,
}: OtpInputProps) {
  const [digits, setDigits] = useState<string[]>(() => Array(length).fill(""));
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus();
  }, [autoFocus]);

  function emit(next: string[]) {
    setDigits(next);
    const code = next.join("");
    onChange?.(code);
    if (code.length === length && next.every((d) => d !== "")) {
      onComplete?.(code);
    }
  }

  function setDigit(i: number, raw: string) {
    const filtered = raw.replace(/\D/g, "");
    if (filtered.length === 0) {
      const next = [...digits];
      next[i] = "";
      emit(next);
      return;
    }
    if (filtered.length > 1) {
      // Paste flow: distribute across remaining boxes.
      const next = [...digits];
      const slice = filtered.slice(0, length - i);
      for (let k = 0; k < slice.length; k++) next[i + k] = slice[k] ?? "";
      emit(next);
      const focusIdx = Math.min(length - 1, i + slice.length);
      refs.current[focusIdx]?.focus();
      return;
    }
    const next = [...digits];
    next[i] = filtered;
    emit(next);
    if (i < length - 1) refs.current[i + 1]?.focus();
  }

  function onKey(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && digits[i] === "" && i > 0) {
      const next = [...digits];
      next[i - 1] = "";
      emit(next);
      refs.current[i - 1]?.focus();
      e.preventDefault();
    }
    if (e.key === "ArrowLeft" && i > 0) {
      refs.current[i - 1]?.focus();
      e.preventDefault();
    }
    if (e.key === "ArrowRight" && i < length - 1) {
      refs.current[i + 1]?.focus();
      e.preventDefault();
    }
  }

  return (
    <fieldset className="flex flex-col gap-2" disabled={disabled}>
      <legend className="text-sm font-medium text-text">{legend}</legend>
      <div
        className={clsx(
          "flex items-center gap-2",
          error && "motion-safe:animate-pulse",
        )}
      >
        {Array.from({ length }).map((_, i) => {
          const isMidGap = length === 6 && i === 3;
          return (
            <div key={i} className="flex items-center gap-2">
              {isMidGap ? <span aria-hidden className="text-text-muted">—</span> : null}
              <input
                ref={(el) => {
                  refs.current[i] = el;
                }}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={1}
                aria-label={digitLabel(i, length)}
                value={digits[i] ?? ""}
                onChange={(e) => setDigit(i, e.target.value)}
                onKeyDown={(e) => onKey(i, e)}
                onPaste={(e) => {
                  const text = e.clipboardData.getData("text").replace(/\D/g, "");
                  if (text) {
                    setDigit(i, text);
                    e.preventDefault();
                  }
                }}
                className={clsx(
                  "h-14 w-12 rounded-md border bg-bg text-center font-mono text-2xl text-text outline-none",
                  error
                    ? "border-2 border-status-error-fg"
                    : digits[i]
                    ? "border-text-muted"
                    : "border-border-strong",
                  "focus:border-primary-600 focus:ring-2 focus:ring-primary-600/30",
                )}
              />
            </div>
          );
        })}
      </div>
      {error && errorMessage ? (
        <p
          role="alert"
          aria-live="polite"
          className="flex items-center gap-1 text-xs text-status-error-fg"
        >
          <span aria-hidden>⚠</span> {errorMessage}
        </p>
      ) : null}
    </fieldset>
  );
}
