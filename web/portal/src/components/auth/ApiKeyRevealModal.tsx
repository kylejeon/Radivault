"use client";

/**
 * <ApiKeyRevealModal> — design-spec-buyer-auth §5.8 + §8 {#api-key-reveal-modal-v1}.
 *
 * One-time plaintext display. Confirm-checkbox-required Done button.
 * sessionStorage persistence so an accidental refresh BEFORE close still
 * shows the key; AFTER close it's gone forever.
 */

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

export type ApiKeyRevealModalProps = {
  open: boolean;
  plaintext: string;
  onClose: () => void;
  // i18n
  title: string;
  warningBold: string;
  warningBody: string;
  copyLabel: string;
  copyToast: string;
  helperBody: string;
  apiDocsLabel: string;
  confirmLabel: string;
  doneLabel: string;
};

export function ApiKeyRevealModal({
  open,
  plaintext,
  onClose,
  title,
  warningBold,
  warningBody,
  copyLabel,
  copyToast,
  helperBody,
  apiDocsLabel,
  confirmLabel,
  doneLabel,
}: ApiKeyRevealModalProps) {
  const [confirmed, setConfirmed] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const copyRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) copyRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(plaintext);
      setToast(copyToast);
      setTimeout(() => setToast(null), 2_500);
    } catch {
      setToast("Copy failed");
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="apikey-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-text/40 p-4"
    >
      <div className="w-full max-w-lg rounded-md bg-bg p-6 shadow-overlay">
        <div className="flex items-start justify-between">
          <h2 id="apikey-modal-title" className="text-base font-semibold text-text">
            🔑 {title}
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
        <div className="mt-3 rounded-md border-l-4 border-status-warning-fg bg-status-warning-bg p-3 text-sm text-text">
          <p className="font-semibold">{warningBold}</p>
          <p className="mt-1 text-text-muted">{warningBody}</p>
        </div>
        <div className="mt-4 flex items-stretch gap-2">
          <code
            data-testid="apikey-plaintext"
            className={clsx(
              "flex-1 select-all break-all rounded-md bg-status-warning-bg px-3 py-2",
              "font-mono text-sm text-text",
            )}
          >
            {plaintext}
          </code>
          <button
            ref={copyRef}
            type="button"
            onClick={copy}
            className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text hover:bg-bg-muted"
          >
            📋 {copyLabel}
          </button>
        </div>
        {toast ? (
          <p
            role="status"
            aria-live="polite"
            className="mt-2 rounded-md bg-status-success-bg px-3 py-1 text-xs text-status-success-fg"
          >
            {toast}
          </p>
        ) : null}
        <p className="mt-3 text-xs text-text-muted">
          {helperBody}{" "}
          <a className="font-medium text-primary-700 underline" href="/docs">
            {apiDocsLabel} →
          </a>
        </p>
        <hr className="my-4 border-border" />
        <label className="flex items-start gap-2 text-sm text-text">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-border-strong text-primary-600 focus:ring-2 focus:ring-primary-600/40"
          />
          <span>{confirmLabel}</span>
        </label>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={!confirmed}
            data-testid="apikey-reveal-done"
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {doneLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
