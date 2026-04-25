"use client";

/**
 * <FormError> top-of-form variant — design-spec-buyer-auth §5.5.1.
 *
 * Field-level errors are handled inline by TextInput / PasswordInput; this
 * component is the bigger banner above the form for ERR_AUTH_INVALID,
 * ERR_EMAIL_TAKEN, ERR_RATE_LIMITED, etc.
 */

import clsx from "clsx";

export type FormErrorProps = {
  title: string;
  hint?: string;
  action?: { label: string; href?: string; onClick?: () => void };
  requestId?: string;
  className?: string;
};

export function FormError({ title, hint, action, requestId, className }: FormErrorProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={clsx(
        "rounded-md border border-status-error-fg bg-status-error-bg px-4 py-3 text-sm",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <span aria-hidden className="text-status-error-fg">⚠</span>
        <div className="flex-1">
          <p className="font-medium text-status-error-fg">{title}</p>
          {hint ? <p className="mt-1 text-text">{hint}</p> : null}
          {action ? (
            <p className="mt-2">
              {action.href ? (
                <a className="font-medium text-primary-700 underline" href={action.href}>
                  {action.label} →
                </a>
              ) : (
                <button
                  type="button"
                  onClick={action.onClick}
                  className="font-medium text-primary-700 underline"
                >
                  {action.label}
                </button>
              )}
            </p>
          ) : null}
          {requestId ? (
            <p className="mt-1 font-mono text-[11px] text-text-muted">
              request_id: {requestId}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
