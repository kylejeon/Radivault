"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorBanner } from "@/components/ErrorBanner";

export function HospitalSignInForm() {
  const router = useRouter();
  const [hospitalId, setHospitalId] = useState("");
  const [token, setToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/hospital/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hospital_id: hospitalId, admin_token: token }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError({ code: body?.error ?? "ERR_AUTH_INVALID", detail: body?.detail });
        setSubmitting(false);
        return;
      }
      router.push("/hospital");
    } catch (err) {
      setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      setSubmitting(false);
    }
  }
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">병원 ID</span>
        <input
          value={hospitalId}
          onChange={(e) => setHospitalId(e.target.value)}
          required
          placeholder="hosp_seoul_amc"
          className="rounded-md border border-surface-border px-3 py-2 font-mono text-sm"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">관리자 토큰</span>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          required
          className="rounded-md border border-surface-border px-3 py-2 font-mono text-sm"
        />
      </label>
      {error ? <ErrorBanner {...error} /> : null}
      <button
        type="submit"
        disabled={submitting || !hospitalId || !token}
        className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40"
      >
        {submitting ? "로그인 중…" : "로그인"}
      </button>
    </form>
  );
}
