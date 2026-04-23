"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PhaseStepper, type BuyerPhase } from "@/components/PhaseStepper";
import { ErrorBanner } from "@/components/ErrorBanner";

type Order = {
  order_id: string;
  state: string;
  buyer_phase: BuyerPhase;
  n_studies: number;
  total_bytes: number;
  submitted_at: string;
  ready_at?: string | null;
  expires_at?: string | null;
  estimated_ready_at?: string | null;
};

export function OrderDetail({ orderId }: { orderId: string }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const res = await fetch(`/api/orders/${orderId}`);
        if (!active) return;
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError({ code: body?.error, detail: body?.detail, requestId: body?.request_id });
          return;
        }
        const body: Order = await res.json();
        setOrder(body);
        setError(null);
        // Keep polling while in non-terminal/non-ready states (FR-A-47).
        const stop: string[] = [
          "ready_to_download",
          "completed",
          "cancelled",
          "expired",
          "failed",
        ];
        if (!stop.includes(body.buyer_phase)) {
          timer = setTimeout(poll, 5000);
        }
      } catch (err) {
        setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
        timer = setTimeout(poll, 10000);
      }
    }
    void poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [orderId]);

  if (error && !order) {
    return <ErrorBanner {...error} />;
  }
  if (!order) {
    return (
      <div className="flex flex-col gap-4">
        <div className="card h-24 animate-pulse" />
        <div className="card h-24 animate-pulse" />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <header>
        <div className="text-sm text-ink-subtle">Order</div>
        <h1 className="font-mono text-2xl font-semibold">{order.order_id}</h1>
        <div className="mt-1 flex gap-6 text-sm text-ink-muted">
          <span>{order.n_studies.toLocaleString()} studies</span>
          <span>{(order.total_bytes / (1024 * 1024)).toFixed(1)} MB</span>
          <span>state: {order.state}</span>
        </div>
      </header>
      <section className="card p-5">
        <h2 className="mb-3 text-sm font-medium text-ink-muted">Progress</h2>
        <PhaseStepper phase={order.buyer_phase} />
        {order.estimated_ready_at ? (
          <p className="mt-3 text-xs text-ink-subtle">
            Estimated ready by:{" "}
            {new Date(order.estimated_ready_at).toLocaleString()}
          </p>
        ) : null}
      </section>
      {order.buyer_phase === "ready_to_download" || order.buyer_phase === "completed" ? (
        <Link
          href={`/orders/${order.order_id}/downloads`}
          className="self-start rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
        >
          View downloads
        </Link>
      ) : null}
    </div>
  );
}
