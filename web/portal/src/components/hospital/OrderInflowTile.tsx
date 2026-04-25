/**
 * OrderInflowTile {#order-inflow-v1} — design-spec §17.7.
 *
 * Big number + last-3 mini list. Buyer ID is ALWAYS rendered as
 * "buyer ****" — never the real opaque id (FR-SH-5 / FR-HO-3.4).
 * That contract is enforced by the component (it ignores any
 * `buyer_id` field on each row and substitutes the masked label).
 */

"use client";

import Link from "next/link";
import { getDict } from "@/lib/i18n";
import { formatRelativeKo } from "./format";

export type OrderInflowItem = {
  // The shape mirrors HospitalOrdersResponse but the `order_id_masked`
  // field is the only identifier we ever surface, and the buyer label is
  // always the dictionary's "buyer ****".
  order_id_masked: string;
  n_studies: number;
  submitted_at: string;
};

export type OrderInflowData = {
  count_this_month: number;
  recent: OrderInflowItem[];
};

export function OrderInflowTile({
  data,
  loading = false,
  testId = "order-inflow-tile",
}: {
  data: OrderInflowData | null;
  loading?: boolean;
  testId?: string;
}) {
  const dict = getDict("ko");

  if (loading) {
    return (
      <div data-testid={testId} data-state="loading" className="flex flex-col gap-2">
        <div className="skeleton h-8 w-24" />
        <div className="skeleton h-3 w-40" />
      </div>
    );
  }
  if (!data || data.count_this_month === 0) {
    return (
      <div
        data-testid={testId}
        data-state="empty"
        className="flex flex-col gap-2"
      >
        <div
          aria-hidden
          className="size-8 rounded-md bg-bg-muted"
        />
        <span className="text-sm text-text-muted">
          {dict.hospital.tile.orderInflowEmpty}
        </span>
      </div>
    );
  }

  return (
    <div data-testid={testId} className="flex flex-col gap-2">
      <Link
        href="/hospital/orders"
        className="text-3xl font-semibold tabular-nums text-text-strong hover:text-teal-700"
      >
        {data.count_this_month.toLocaleString("ko-KR")} 건
      </Link>
      <div className="text-xs text-text-muted">
        {dict.hospital.tile.orderInflowSubtitle}
      </div>
      <ul className="mt-1 flex flex-col gap-1 text-xs">
        {data.recent.slice(0, 3).map((o) => (
          <li
            key={o.order_id_masked + o.submitted_at}
            className="grid grid-cols-[1fr_auto_auto] items-center gap-2"
          >
            <span className="text-text-muted">
              {/* Buyer name is ALWAYS masked — see FR-SH-5 / FR-HO-3.4. */}
              {dict.hospital.tile.buyerMasked}
            </span>
            <span className="tabular-nums">{o.n_studies.toLocaleString("ko-KR")} study</span>
            <span className="text-text-muted">
              {formatRelativeKo(o.submitted_at)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
