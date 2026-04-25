"use client";

/**
 * <TextInput> — design-spec-buyer-auth §5.1 {#text-input-v1}.
 *
 * Single-line text/email field with label, helper, and error states.
 * Used by signup, signin, password-reset, and account-delete forms.
 */

import { forwardRef } from "react";
import clsx from "clsx";

export type TextInputProps = {
  id: string;
  label: string;
  type?: "email" | "text" | "number";
  required?: boolean;
  helper?: string;
  error?: string | null;
  autoComplete?: string;
  maxLength?: number;
  placeholder?: string;
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  readOnly?: boolean;
  // i18n
  requiredLabel?: string; // "* required" | "* 필수"
  // hidden input behaviour for confirm-typing
  inputMode?: "text" | "email" | "numeric";
  spellCheck?: boolean;
};

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  function TextInput(
    {
      id,
      label,
      type = "text",
      required = false,
      helper,
      error,
      autoComplete,
      maxLength,
      placeholder,
      value,
      onChange,
      disabled = false,
      readOnly = false,
      requiredLabel = "* required",
      inputMode,
      spellCheck = true,
    },
    ref,
  ) {
    const errorId = error ? `${id}-error` : undefined;
    const helperId = helper && !error ? `${id}-helper` : undefined;
    const describedBy = errorId ?? helperId;
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
        <input
          ref={ref}
          id={id}
          type={type}
          required={required}
          aria-required={required || undefined}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={describedBy}
          autoComplete={autoComplete}
          maxLength={maxLength}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          readOnly={readOnly}
          inputMode={inputMode}
          spellCheck={spellCheck}
          className={clsx(
            "h-11 w-full rounded-md border bg-bg px-4 text-base text-text",
            "outline-none transition-colors",
            "placeholder:text-text-muted/60",
            error
              ? "border-2 border-status-error-fg focus:border-status-error-fg focus:ring-2 focus:ring-status-error-fg/30"
              : "border-border-strong hover:border-text-muted focus:border-primary-600 focus:ring-2 focus:ring-primary-600/30",
            disabled && "cursor-not-allowed bg-bg-muted opacity-60",
            readOnly && "bg-bg-muted",
          )}
        />
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
      </div>
    );
  },
);
