"use client";

import { useState } from "react";
import { getDict, type Locale } from "@/lib/i18n";

/**
 * AccountClient — design-spec-portal-redesign §12.4.
 * FR-BP-13. Pure presentation; the masked API key arrives from the server
 * page wrapper so the raw httpOnly value never lives in the browser bundle.
 */
export function AccountClient({
  apiKeyMasked,
  buyerId,
  tier,
  signedInAt,
  locale = "en",
}: {
  apiKeyMasked: string;
  buyerId: string;
  tier: string;
  signedInAt: number;
  locale?: Locale;
}) {
  const dict = getDict(locale);
  const [revealOpen, setRevealOpen] = useState(false);

  const created = new Date(signedInAt).toLocaleDateString(
    locale === "ko" ? "ko-KR" : "en-US",
  );

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-2xl font-semibold text-text-strong">
        {dict.account.pageTitle}
      </h1>

      {/* Profile */}
      <section
        aria-label={dict.account.profileTitle}
        className="rounded-md border border-border bg-bg p-5"
      >
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
          {dict.account.profileTitle}
        </h2>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 text-sm">
          <dt className="text-text-muted">{dict.account.profileFields.buyerId}</dt>
          <dd className="font-mono text-text">{buyerId}</dd>
          <dt className="text-text-muted">{dict.account.profileFields.tier}</dt>
          <dd className="text-text">{tier}</dd>
          <dt className="text-text-muted">
            {dict.account.profileFields.createdAt}
          </dt>
          <dd className="text-text">{created}</dd>
          <dt className="text-text-muted">
            {dict.account.profileFields.quotaRemaining}
          </dt>
          <dd className="text-text-muted">— (v0.1.1)</dd>
        </dl>
      </section>

      {/* API keys */}
      <section
        aria-label={dict.account.apiKeysTitle}
        className="rounded-md border border-border bg-bg p-5"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            {dict.account.apiKeysTitle}
          </h2>
          <button
            type="button"
            disabled
            title="v0.1.1"
            className="rounded-md border border-border px-3 py-1 text-xs text-text-muted disabled:opacity-50"
          >
            + {dict.account.issueNewKey}
          </button>
        </div>
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-text-muted">
            <tr>
              <th className="pb-2 text-left">kid prefix</th>
              <th className="pb-2 text-left">created</th>
              <th className="pb-2 text-left">status</th>
              <th className="pb-2 text-right">actions</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-border">
              <td className="py-2">
                <code
                  data-testid="account-apikey-masked"
                  className="font-mono text-xs text-text"
                >
                  {apiKeyMasked}
                </code>
              </td>
              <td className="py-2 text-text-muted">{created}</td>
              <td className="py-2">
                <span className="rounded-pill bg-status-success-bg px-2 py-0.5 text-[11px] font-medium text-status-success-fg">
                  active
                </span>
              </td>
              <td className="py-2 text-right">
                <button
                  type="button"
                  onClick={() => setRevealOpen(true)}
                  data-testid="account-reveal-once"
                  className="rounded-md border border-border px-2 py-1 text-xs text-text-muted hover:bg-bg-muted"
                >
                  {dict.account.revealOnce}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* Billing */}
      <section
        aria-label={dict.account.billingTitle}
        className="rounded-md border border-border bg-bg p-5"
      >
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
          {dict.account.billingTitle}
        </h2>
        <p className="text-sm text-text-muted">{dict.account.billingBody}</p>
        <a
          href="mailto:billing@radivault.io"
          className="mt-2 inline-flex text-sm font-medium text-primary-700 hover:underline"
        >
          {dict.account.contactBilling} →
        </a>
      </section>

      {revealOpen ? (
        <RevealModal
          locale={locale}
          onClose={() => setRevealOpen(false)}
        />
      ) : null}
    </div>
  );
}

function RevealModal({
  locale,
  onClose,
}: {
  locale: Locale;
  onClose: () => void;
}) {
  const dict = getDict(locale);
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={dict.account.revealOnce}
      className="fixed inset-0 z-50 flex items-center justify-center bg-text/30 p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-md bg-bg p-6 shadow-overlay"
      >
        <h2 className="mb-2 text-base font-semibold text-text">
          {dict.account.revealOnce}
        </h2>
        <p className="text-sm text-text-muted">{dict.account.revealStubBody}</p>
        <div className="mt-4 flex justify-end gap-2">
          <a
            href="mailto:support@radivault.io?subject=API%20key%20rotation"
            className="rounded-md bg-primary-600 px-3 py-1.5 text-sm font-semibold text-white"
          >
            {dict.account.revealStubCta}
          </a>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-bg-muted"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
