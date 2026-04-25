"use client";

/**
 * <ApiKeyMaskedDisplay> — design-spec-buyer-auth §5.6.
 *
 * /account API Keys card. Single-key model (v0.1). Kyle Q1: Copy button
 * copies the FULL masked string (UX over paranoia).
 */

import { useState } from "react";
import clsx from "clsx";

export type ApiKeyMaskedDisplayProps = {
  kid: string | null;
  masked: string | null;
  tier: string;
  createdAt: string | null;
  lastUsedAt: string | null;
  onRegenerate: () => void;
  onRevoke: () => void;
  busy?: boolean;
  // i18n
  cardTitle: string;
  tierLabel: string;
  metaLabel: (created: string, last: string | null) => string;
  copyLabel: string;
  copyToast: string;
  regenerateLabel: string;
  revokeLabel: string;
  emptyTitle: string;
  emptyBody: string;
  generateLabel: string;
};

export function ApiKeyMaskedDisplay({
  kid,
  masked,
  tier,
  createdAt,
  lastUsedAt,
  onRegenerate,
  onRevoke,
  busy = false,
  cardTitle,
  tierLabel,
  metaLabel,
  copyLabel,
  copyToast,
  regenerateLabel,
  revokeLabel,
  emptyTitle,
  emptyBody,
  generateLabel,
}: ApiKeyMaskedDisplayProps) {
  const [toast, setToast] = useState<string | null>(null);

  if (!kid || !masked) {
    return (
      <div className="rounded-md border border-border bg-bg p-5">
        <p className="font-medium text-text">{emptyTitle}</p>
        <p className="mt-1 text-sm text-text-muted">{emptyBody}</p>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={busy}
          className="mt-3 rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {generateLabel}
        </button>
      </div>
    );
  }

  async function copyMasked() {
    try {
      await navigator.clipboard.writeText(masked!);
      setToast(copyToast);
      setTimeout(() => setToast(null), 2_500);
    } catch {
      setToast("Copy failed");
      setTimeout(() => setToast(null), 2_500);
    }
  }

  return (
    <div className="rounded-md border border-border bg-bg p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">{cardTitle}</h3>
        <span className="rounded-pill bg-primary-50 px-2 py-0.5 text-[11px] font-medium text-primary-700">
          {tierLabel} {tier}
        </span>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <code
          data-testid="account-apikey-masked"
          className="flex-1 rounded-md bg-bg-muted px-3 py-2 font-mono text-sm text-text"
        >
          {masked}
        </code>
        <button
          type="button"
          onClick={copyMasked}
          className={clsx(
            "rounded-md border border-border px-3 py-2 text-sm font-medium text-text",
            "hover:bg-bg-muted focus:outline-none focus:ring-2 focus:ring-primary-600/40",
          )}
        >
          {copyLabel}
        </button>
      </div>
      <p className="mt-2 text-xs text-text-muted">
        {metaLabel(createdAt ?? "—", lastUsedAt)}
      </p>
      <hr className="my-4 border-border" />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onRegenerate}
          disabled={busy}
          data-testid="account-regenerate"
          className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text hover:bg-bg-muted disabled:opacity-50"
        >
          {regenerateLabel}
        </button>
        <button
          type="button"
          onClick={onRevoke}
          disabled={busy}
          data-testid="account-revoke"
          className="rounded-md border border-status-error-fg px-3 py-1.5 text-sm font-medium text-status-error-fg hover:bg-status-error-bg disabled:opacity-50"
        >
          {revokeLabel}
        </button>
      </div>
      {toast ? (
        <div
          role="status"
          aria-live="polite"
          className="mt-3 rounded-md bg-status-success-bg px-3 py-1.5 text-xs text-status-success-fg"
        >
          {toast}
        </div>
      ) : null}
    </div>
  );
}
