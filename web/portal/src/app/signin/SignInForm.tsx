"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorBanner } from "@/components/ErrorBanner";

export function SignInForm() {
  const router = useRouter();
  const [key, setKey] = useState("");
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: key }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError({
          code: body?.error ?? "ERR_AUTH_INVALID",
          detail: body?.detail,
          requestId: body?.request_id,
        });
        setSubmitting(false);
        return;
      }
      router.push("/search");
    } catch (err) {
      setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-ink">API key</span>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="rv_live_…"
          required
          className="rounded-md border border-surface-border px-3 py-2 font-mono text-sm focus:border-primary focus:outline-none"
        />
      </label>
      {error ? (
        <ErrorBanner code={error.code} requestId={error.requestId} detail={error.detail} />
      ) : null}
      <button
        type="submit"
        disabled={submitting || !key}
        className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40"
      >
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
