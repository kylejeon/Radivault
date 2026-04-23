"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";

type Order = {
  order_id: string;
  state: string;
  buyer_phase: string;
  n_studies: number;
  submitted_at: string;
  estimated_ready_at?: string | null;
};

export function OrdersList() {
  const [items, setItems] = useState<Order[] | null>(null);
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );
  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/orders");
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError({ code: body?.error, detail: body?.detail, requestId: body?.request_id });
          return;
        }
        const body = await res.json();
        setItems(body.items ?? []);
      } catch (err) {
        setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      }
    })();
  }, []);

  if (error) return <ErrorBanner {...error} />;
  if (items === null) {
    return (
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="card h-14 animate-pulse" />
        ))}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <EmptyState
        title="You haven't placed any orders"
        body="Start by searching for a cohort in the Search page."
        ctaHref="/search"
        ctaLabel="Go to Search"
      />
    );
  }
  return (
    <div className="card">
      <table className="w-full">
        <thead>
          <tr className="border-b border-surface-border text-left text-xs uppercase text-ink-subtle">
            <th className="px-4 py-2">Order id</th>
            <th className="px-4 py-2">Phase</th>
            <th className="px-4 py-2">Studies</th>
            <th className="px-4 py-2">Submitted</th>
            <th className="px-4 py-2">ETA</th>
          </tr>
        </thead>
        <tbody>
          {items.map((o) => (
            <tr key={o.order_id} className="border-b border-surface-border last:border-b-0">
              <td className="px-4 py-3">
                <Link href={`/orders/${o.order_id}`} className="font-mono text-sm text-primary">
                  {o.order_id.slice(-8)}
                </Link>
              </td>
              <td className="px-4 py-3 text-sm">{o.buyer_phase}</td>
              <td className="px-4 py-3 tabular-nums">{o.n_studies}</td>
              <td className="px-4 py-3 text-xs text-ink-muted">
                {o.submitted_at ? new Date(o.submitted_at).toLocaleString() : "—"}
              </td>
              <td className="px-4 py-3 text-xs text-ink-muted">
                {o.estimated_ready_at
                  ? new Date(o.estimated_ready_at).toLocaleTimeString()
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
