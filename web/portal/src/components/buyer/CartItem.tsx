"use client";

import Link from "next/link";
import { BuyerModalityBadge } from "./ModalityBadge";

/**
 * CartItem {#cart-item-v1} — design-spec-portal-redesign §11.6.
 * FR-BP-9.
 *
 * Two variants:
 *   - `mini`: compact 320 px sidebar entry on `/search` cohort sidebar
 *             (modality badge + 2-line summary + remove button).
 *   - `full`: data-table row on `/orders/new` (remove · modality · summary ·
 *             hospital · size · year).
 */

export type CartItemData = {
  pseudo_study_uid: string;
  modality: string | null;
  body_part: string | null;
  age_bucket: string | null;
  sex: string | null;
  total_bytes: number;
  hospital_opaque_id: string | null;
  study_date_shifted: string | null;
};

export type CartItemProps = {
  item: CartItemData;
  variant: "mini" | "full";
  onRemove?: () => void;
  locale?: "en" | "ko";
};

function shortHospital(id: string | null): string {
  if (!id) return "—";
  return `HOSP-${id.slice(0, 6).toUpperCase()}`;
}

function sizeMb(b: number): string {
  return (b / (1024 * 1024)).toFixed(0);
}

function yearOf(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 4);
}

export function CartItem({ item, variant, onRemove, locale = "en" }: CartItemProps) {
  const remove = locale === "ko" ? "제거" : "Remove";
  const detailHref = `/studies/${encodeURIComponent(item.pseudo_study_uid)}`;
  const summary = [item.body_part, item.age_bucket, item.sex]
    .filter(Boolean)
    .join(" · ") || "—";

  if (variant === "mini") {
    return (
      <div
        data-testid="cart-item-mini"
        className="flex items-start gap-2 border-b border-border py-2 last:border-b-0"
      >
        <button
          type="button"
          onClick={onRemove}
          aria-label={`${remove}: ${item.pseudo_study_uid.slice(-8)}`}
          className="text-text-muted hover:text-status-error-fg"
        >
          ✕
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <BuyerModalityBadge modality={item.modality} size="sm" />
            <Link
              href={detailHref}
              target="_blank"
              rel="noopener"
              className="truncate text-sm font-medium text-text hover:underline"
            >
              {item.body_part ?? "—"}
            </Link>
          </div>
          <div className="mt-0.5 truncate text-xs text-text-muted">
            {item.age_bucket ?? "—"} · {item.sex ?? "—"} ·{" "}
            <span className="font-mono">
              {shortHospital(item.hospital_opaque_id)}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="cart-item-full"
      className="flex items-center gap-3 border-b border-border px-2 py-2.5 text-sm last:border-b-0"
    >
      <button
        type="button"
        onClick={onRemove}
        aria-label={`${remove}: ${item.pseudo_study_uid.slice(-8)}`}
        className="text-text-muted hover:text-status-error-fg"
      >
        ✕
      </button>
      <div className="w-16 shrink-0">
        <BuyerModalityBadge modality={item.modality} />
      </div>
      <div className="min-w-0 flex-1 truncate">
        <Link
          href={detailHref}
          target="_blank"
          rel="noopener"
          className="text-text hover:underline"
        >
          {summary}
        </Link>
      </div>
      <div className="w-28 shrink-0 font-mono text-xs text-text-muted">
        {shortHospital(item.hospital_opaque_id)}
      </div>
      <div className="w-20 shrink-0 text-right font-mono tabular-nums text-text">
        {sizeMb(item.total_bytes)} MB
      </div>
      <div className="w-16 shrink-0 text-right text-text-muted">
        {yearOf(item.study_date_shifted)}
      </div>
    </div>
  );
}

/**
 * Empty cohort placeholder — design-spec §11.6 / K-10 (line-art placeholder).
 */
export function CartEmpty({ locale = "en" }: { locale?: "en" | "ko" }) {
  const text =
    locale === "ko"
      ? "결과에서 study 를 선택해 코호트를 구성하세요."
      : "Select studies from results to build cohort.";
  return (
    <div
      data-testid="cart-empty"
      className="flex flex-col items-center gap-2 rounded-md border border-dashed border-border bg-bg-muted px-4 py-8 text-center"
    >
      <div aria-hidden className="text-2xl text-text-muted">▦</div>
      <p className="text-xs text-text-muted">{text}</p>
    </div>
  );
}
