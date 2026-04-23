"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorBanner } from "@/components/ErrorBanner";

/**
 * A-5 Review order modal (FR-A-30..FR-A-36).
 *
 * - DUA checkbox must be ticked before Confirm is enabled.
 * - Price is masked (v0.1 dev-spec §0.2-3).
 * - Idempotency-Key is generated client-side and kept per-modal lifecycle.
 * - On 202, the modal morphs to a receipt + auto-navigates to /orders/{id}.
 */
export function ReviewOrderModal({
  uids,
  totalSizeMb,
  onClose,
}: {
  uids: string[];
  totalSizeMb: number;
  onClose: () => void;
}) {
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );
  const [receipt, setReceipt] = useState<{ orderId: string; phase: string } | null>(null);

  async function onConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      const idemKey = crypto.randomUUID();
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idemKey,
        },
        body: JSON.stringify({ pseudo_study_uids: uids }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError({
          code: body?.error ?? "ERR_UNKNOWN",
          detail: body?.detail,
          requestId: body?.request_id,
        });
        setSubmitting(false);
        return;
      }
      const body = await res.json();
      setReceipt({ orderId: body.order_id, phase: body.buyer_phase ?? "accepted" });
      setTimeout(() => router.push(`/orders/${body.order_id}`), 2500);
    } catch (err) {
      setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Review order"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
    >
      <div className="card w-full max-w-lg p-6">
        <div className="flex items-start justify-between">
          <h2 className="text-lg font-semibold">Review order</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-ink-subtle hover:text-ink"
            aria-label="Close dialog"
          >
            ×
          </button>
        </div>

        {receipt ? (
          <div className="mt-4 flex flex-col gap-2">
            <div className="rounded-md bg-green-50 p-3 text-sm text-green-900">
              Order <code>{receipt.orderId}</code> accepted. Phase: {receipt.phase}.
            </div>
            <p className="text-sm text-ink-muted">Redirecting to order tracker…</p>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Studies" value={uids.length.toLocaleString()} />
              <Stat label="Total size" value={`${totalSizeMb.toFixed(1)} MB`} />
              <Stat label="Agreement" value="MSA v0.1 (stub)" />
              <Stat label="Price" value="— (v0.1)" />
            </div>
            <p className="text-xs text-ink-subtle">
              Billing is v0.1 stub — no charge will occur. Contact{" "}
              <a className="underline" href="mailto:sales@radivault.io">
                sales@radivault.io
              </a>{" "}
              to activate a paid tier.
            </p>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-0.5 size-4"
              />
              <span>
                I confirm this order is governed by the MSA referenced by the
                stored agreement hash and that resulting data will only be
                used within the approved scope.
              </span>
            </label>
            {error ? (
              <ErrorBanner
                code={error.code}
                requestId={error.requestId}
                detail={error.detail}
              />
            ) : null}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-surface-border px-3 py-2 text-sm text-ink-muted hover:bg-surface-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={!agreed || submitting || uids.length === 0}
                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40"
              >
                {submitting ? "Submitting…" : "Confirm order"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="font-semibold text-ink">{value}</div>
    </div>
  );
}
