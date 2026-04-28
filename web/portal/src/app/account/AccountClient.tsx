"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiKeyMaskedDisplay } from "@/components/auth/ApiKeyMaskedDisplay";
import { ApiKeyRevealModal } from "@/components/auth/ApiKeyRevealModal";
import { getDict, type Locale } from "@/lib/i18n";

const SESSION_REVEAL_KEY = "rv_apikey_reveal_once";

/**
 * AccountClient — design-spec-buyer-auth §6 wireframe + §5.6.
 *
 * v0.2 changes vs v0.1 stub:
 *   - API Keys section uses <ApiKeyMaskedDisplay> with Regenerate / Revoke
 *     wired to /api/account/api-key.
 *   - On Regenerate success, ApiKeyRevealModal opens with the one-time
 *     plaintext (also stashed in sessionStorage so an accidental refresh
 *     before "Done" preserves the modal).
 *   - Profile section reads buyerId/email/tier/createdAt from props
 *     (server-rendered).
 */
export function AccountClient({
  buyerId,
  email,
  tier,
  signedInAt,
  initialKey,
  locale = "en",
}: {
  buyerId: string;
  email: string | null;
  tier: string;
  signedInAt: number;
  initialKey: {
    kid: string | null;
    masked: string | null;
    createdAt: string | null;
    lastUsedAt: string | null;
  };
  locale?: Locale;
}) {
  const router = useRouter();
  const dict = getDict(locale);
  const t = dict.auth;

  const [keyState, setKeyState] = useState(initialKey);
  const [busy, setBusy] = useState(false);
  const [revealKey, setRevealKey] = useState<string | null>(null);
  const [confirmRegen, setConfirmRegen] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteEmail, setDeleteEmail] = useState("");

  // Restore any unconfirmed reveal modal across accidental refresh.
  useEffect(() => {
    try {
      const stash = sessionStorage.getItem(SESSION_REVEAL_KEY);
      if (stash) setRevealKey(stash);
    } catch {
      // ignore
    }
  }, []);

  const created = new Date(signedInAt).toLocaleDateString(
    locale === "ko" ? "ko-KR" : "en-US",
  );

  async function postApiKeyAction(action: "generate" | "regenerate") {
    setBusy(true);
    try {
      const res = await fetch("/api/account/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(body?.error?.message ?? t.common.genericError);
        return;
      }
      try {
        sessionStorage.setItem(SESSION_REVEAL_KEY, body.plaintext);
      } catch {
        // ignore
      }
      setRevealKey(body.plaintext);
      setKeyState({
        kid: body.kid,
        masked: body.masked,
        createdAt: new Date().toISOString(),
        lastUsedAt: null,
      });
    } finally {
      setBusy(false);
      setConfirmRegen(false);
    }
  }

  // Defer-mint flow (Kyle 2026-04-27): empty-state Generate button skips
  // the "Regenerate?" confirmation modal — there is no key to overwrite.
  function generate() {
    void postApiKeyAction("generate");
  }
  function regenerate() {
    void postApiKeyAction("regenerate");
  }

  async function revoke() {
    setBusy(true);
    try {
      const res = await fetch("/api/account/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "revoke" }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        alert(body?.error?.message ?? t.common.genericError);
        return;
      }
      setKeyState({ kid: null, masked: null, createdAt: null, lastUsedAt: null });
    } finally {
      setBusy(false);
      setConfirmRevoke(false);
    }
  }

  async function deleteAccount() {
    setBusy(true);
    try {
      const res = await fetch("/api/auth/account", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emailConfirmation: deleteEmail }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        alert(body?.error?.message ?? t.common.genericError);
        return;
      }
      router.push("/");
    } finally {
      setBusy(false);
      setConfirmDelete(false);
    }
  }

  function onRevealClose() {
    try {
      sessionStorage.removeItem(SESSION_REVEAL_KEY);
    } catch {
      // ignore
    }
    setRevealKey(null);
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-text-strong">
          {dict.account.pageTitle}
        </h1>
        {/*
          Sign-out moved here when MarketplaceNav was rewritten in
          bab29b5 (the in-nav form button was dropped). Posts to the
          legacy /api/session/delete which destroys the iron-session
          cookie and 303-redirects to "/". Form-based so it works
          without JavaScript.
        */}
        <form action="/api/session/delete" method="post">
          <button
            type="submit"
            data-testid="account-signout"
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-muted hover:bg-bg-muted hover:text-text"
          >
            {dict.buyerNav.signOut}
          </button>
        </form>
      </div>

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
          {email ? (
            <>
              <dt className="text-text-muted">{dict.account.profileFields.email}</dt>
              <dd className="text-text">{email}</dd>
            </>
          ) : null}
          <dt className="text-text-muted">{dict.account.profileFields.tier}</dt>
          <dd className="text-text">{tier}</dd>
          <dt className="text-text-muted">
            {dict.account.profileFields.createdAt}
          </dt>
          <dd className="text-text">{created}</dd>
        </dl>
      </section>

      <section aria-label={dict.account.apiKeysTitle}>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
          {dict.account.apiKeysTitle}
        </h2>
        <ApiKeyMaskedDisplay
          kid={keyState.kid}
          masked={keyState.masked}
          tier={tier}
          createdAt={keyState.createdAt}
          lastUsedAt={keyState.lastUsedAt}
          busy={busy}
          onRegenerate={() => setConfirmRegen(true)}
          onGenerate={generate}
          onRevoke={() => setConfirmRevoke(true)}
          cardTitle={t.apiKeyCard.cardTitle}
          tierLabel={t.apiKeyCard.tierLabel}
          metaLabel={(c, l) =>
            `${dict.account.profileFields.createdAt} ${c}` +
            (l ? ` · ${l}` : "")
          }
          copyLabel={t.apiKeyCard.copyMasked}
          copyToast={t.apiKeyCard.copyToast}
          regenerateLabel={t.apiKeyCard.regenerate}
          revokeLabel={t.apiKeyCard.revoke}
          emptyTitle={t.apiKeyCard.emptyTitle}
          emptyBody={t.apiKeyCard.emptyBody}
          generateLabel={t.apiKeyCard.generate}
        />
      </section>

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

      {/* Danger zone — account delete (FR-AUTH-11) */}
      <section className="rounded-md border border-status-error-fg/40 bg-status-error-bg/30 p-5">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-status-error-fg">
          Danger zone
        </h2>
        <p className="text-sm text-text">
          Delete this account and revoke all API keys. 30-day grace period
          before permanent removal.
        </p>
        <button
          type="button"
          onClick={() => setConfirmDelete(true)}
          data-testid="account-delete-trigger"
          className="mt-3 rounded-md border border-status-error-fg px-3 py-1.5 text-sm font-medium text-status-error-fg hover:bg-status-error-bg"
        >
          Delete account
        </button>
      </section>

      {/* Confirmation modals (Kyle Q2 default = centered standard modals) */}
      {confirmRegen ? (
        <ConfirmModal
          title={`${t.apiKeyCard.regenerate}?`}
          body="The current key will be revoked immediately and a new key will be issued. The plaintext will be shown ONCE."
          confirmLabel={t.apiKeyCard.regenerate}
          onConfirm={regenerate}
          onCancel={() => setConfirmRegen(false)}
          busy={busy}
        />
      ) : null}
      {confirmRevoke ? (
        <ConfirmModal
          title={`${t.apiKeyCard.revoke}?`}
          body="Programmatic access will be disabled until you generate a new key."
          confirmLabel={t.apiKeyCard.revoke}
          danger
          onConfirm={revoke}
          onCancel={() => setConfirmRevoke(false)}
          busy={busy}
        />
      ) : null}
      {confirmDelete ? (
        <DeleteAccountModal
          email={email ?? ""}
          value={deleteEmail}
          onChange={setDeleteEmail}
          onConfirm={deleteAccount}
          onCancel={() => {
            setConfirmDelete(false);
            setDeleteEmail("");
          }}
          busy={busy}
        />
      ) : null}

      <ApiKeyRevealModal
        open={revealKey !== null}
        plaintext={revealKey ?? ""}
        onClose={onRevealClose}
        title={t.revealKey.title}
        warningBold={t.revealKey.warningBold}
        warningBody={t.revealKey.warningBody}
        copyLabel={t.revealKey.copy}
        copyToast={t.revealKey.copyToast}
        helperBody={t.revealKey.helperBody}
        apiDocsLabel={t.revealKey.apiDocs}
        confirmLabel={t.revealKey.confirm}
        doneLabel={t.revealKey.done}
      />
    </div>
  );
}

function ConfirmModal({
  title,
  body,
  confirmLabel,
  onConfirm,
  onCancel,
  busy,
  danger = false,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy: boolean;
  danger?: boolean;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-text/40 p-4"
    >
      <div className="w-full max-w-md rounded-md bg-bg p-6 shadow-overlay">
        <h2 className="text-base font-semibold text-text">{title}</h2>
        <p className="mt-2 text-sm text-text-muted">{body}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-bg-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={
              danger
                ? "rounded-md bg-status-error-fg px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                : "rounded-md bg-primary-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function DeleteAccountModal({
  email,
  value,
  onChange,
  onConfirm,
  onCancel,
  busy,
}: {
  email: string;
  value: string;
  onChange: (s: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const matches = value.toLowerCase() === email.toLowerCase() && email.length > 0;
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-text/40 p-4"
    >
      <div className="w-full max-w-md rounded-md bg-bg p-6 shadow-overlay">
        <h2 className="text-base font-semibold text-status-error-fg">
          Delete account?
        </h2>
        <p className="mt-2 text-sm text-text">
          This soft-deletes your account, revokes all keys, and starts a 30-day
          hard-delete grace period. To confirm, type your email below.
        </p>
        <input
          type="email"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={email}
          className="mt-3 h-11 w-full rounded-md border border-border-strong bg-bg px-3 text-base text-text"
          data-testid="account-delete-email"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-bg-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy || !matches}
            data-testid="account-delete-confirm"
            className="rounded-md bg-status-error-fg px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Delete account
          </button>
        </div>
      </div>
    </div>
  );
}
