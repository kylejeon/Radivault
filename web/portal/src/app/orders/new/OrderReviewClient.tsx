"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ErrorBanner } from "@/components/ErrorBanner";
import { CartItem, type CartItemData } from "@/components/buyer/CartItem";
import { FederatedSignal } from "@/components/buyer/FederatedSignal";
import { getDict, type Locale } from "@/lib/i18n";

const COHORT_STORAGE_KEY = "radivault.cohort.v1";
const DUA_VERSION = "v0.1.0"; // K-12 deferred — hardcoded.

type CohortMap = Record<string, CartItemData>;

function loadCohort(): CohortMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(COHORT_STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as CohortMap;
  } catch {
    return {};
  }
}

function saveCohort(cohort: CohortMap) {
  try {
    window.sessionStorage.setItem(COHORT_STORAGE_KEY, JSON.stringify(cohort));
  } catch {
    /* ignore */
  }
}

function countByModality(items: CartItemData[]): { key: string; count: number }[] {
  const tally = new Map<string, number>();
  for (const it of items) {
    const k = (it.modality ?? "—").toUpperCase();
    tally.set(k, (tally.get(k) ?? 0) + 1);
  }
  return Array.from(tally.entries())
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count);
}

function countByHospital(items: CartItemData[]): { key: string; count: number }[] {
  const tally = new Map<string, number>();
  for (const it of items) {
    const k = it.hospital_opaque_id
      ? `HOSP-${it.hospital_opaque_id.slice(0, 6).toUpperCase()}`
      : "—";
    tally.set(k, (tally.get(k) ?? 0) + 1);
  }
  return Array.from(tally.entries())
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count);
}

export function OrderReviewClient({ locale = "en" }: { locale?: Locale }) {
  const dict = getDict(locale);
  const router = useRouter();
  const [cohort, setCohort] = useState<CohortMap>({});
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{
    code?: string;
    detail?: string;
    requestId?: string;
  } | null>(null);

  useEffect(() => {
    setCohort(loadCohort());
  }, []);

  const items = useMemo(() => Object.values(cohort), [cohort]);
  const totalBytes = useMemo(
    () => items.reduce((sum, it) => sum + it.total_bytes, 0),
    [items],
  );
  const hospitalCount = useMemo(() => {
    const set = new Set<string>();
    for (const it of items)
      if (it.hospital_opaque_id) set.add(it.hospital_opaque_id);
    return set.size;
  }, [items]);
  const modalityBreakdown = useMemo(() => countByModality(items), [items]);
  const hospitalBreakdown = useMemo(() => countByHospital(items), [items]);

  function removeItem(uid: string) {
    setCohort((prev) => {
      const next = { ...prev };
      delete next[uid];
      saveCohort(next);
      return next;
    });
  }

  async function placeOrder() {
    if (items.length === 0 || !agreed) return;
    setSubmitting(true);
    setError(null);
    try {
      const idemKey = crypto.randomUUID();
      // FR-BP-9 / AC-BP-8 — auto-inject allowed_hospitals scope so the
      // fulfillment service only fans out to the hospitals already
      // represented in the cohort. HIGH-4 fix from qa-report-portal-redesign.
      const allowedHospitals = Array.from(
        new Set(
          items
            .map((i) => i.hospital_opaque_id ?? null)
            .filter((v): v is string => !!v),
        ),
      ).sort();
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idemKey,
        },
        body: JSON.stringify({
          pseudo_study_uids: items.map((i) => i.pseudo_study_uid),
          allowed_hospitals: allowedHospitals,
          notes: `dua_version=${DUA_VERSION}`,
        }),
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
      // Clear the cohort so the buyer doesn't accidentally re-submit.
      saveCohort({});
      setCohort({});
      router.push(`/orders/${body.order_id}`);
    } catch (err) {
      setError({
        code: "ERR_UPSTREAM_UNAVAILABLE",
        detail: String(err),
      });
      setSubmitting(false);
    }
  }

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-border bg-bg-muted px-6 py-12 text-center">
        <h1 className="text-lg font-semibold text-text">
          {dict.orders.cohortEmptyTitle}
        </h1>
        <p className="mx-auto mt-2 max-w-prose text-sm text-text-muted">
          {dict.orders.cohortEmptyBody}
        </p>
        <Link
          href="/search"
          className="mt-4 inline-flex rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white"
        >
          ← {dict.orders.backToSearch}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-semibold text-text-strong">
          {dict.orders.cartTitle}
        </h1>
        <div className="mt-1">
          <FederatedSignal
            studyCount={items.length}
            hospitalCount={hospitalCount}
            variant="mini"
            locale={locale}
          />
        </div>
      </header>

      <div className="grid grid-cols-1 gap-5 desktop:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {/* Left — full cart */}
        <section
          aria-label={dict.orders.cartTitle}
          className="rounded-md border border-border bg-bg p-1"
        >
          {items.map((it) => (
            <CartItem
              key={it.pseudo_study_uid}
              item={it}
              variant="full"
              onRemove={() => removeItem(it.pseudo_study_uid)}
              locale={locale}
            />
          ))}
        </section>

        {/* Right — distribution */}
        <aside className="flex flex-col gap-4">
          <DistributionCard
            title={dict.orders.distributionTitle}
            rows={hospitalBreakdown}
          />
          <DistributionCard
            title={dict.orders.modalityBreakdownTitle}
            rows={modalityBreakdown}
          />
        </aside>
      </div>

      {/* Order summary + DUA */}
      <section
        aria-label="Order summary"
        className="rounded-md border border-border bg-bg p-5"
      >
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-muted">
          ORDER SUMMARY
        </h2>
        <dl className="mb-4 grid grid-cols-2 gap-y-1 text-sm">
          <SummaryRow label={dict.orders.summaryStudies}>
            {items.length}
          </SummaryRow>
          <SummaryRow label={dict.orders.summaryHospitals}>
            {hospitalCount}
          </SummaryRow>
          <SummaryRow label={dict.orders.summaryTotalSize}>
            <span className="font-mono">
              {(totalBytes / (1024 * 1024)).toFixed(1)} MB
            </span>
          </SummaryRow>
          <SummaryRow label={dict.orders.summaryEstimatedCost}>
            <span className="text-text-muted">
              — {dict.orders.pricingMasked}
            </span>
          </SummaryRow>
        </dl>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            data-testid="dua-checkbox"
            className="mt-0.5 size-4"
          />
          <span>
            {dict.orders.duaCheckbox}{" "}
            <a
              href="mailto:legal@radivault.io?subject=DUA%20v0.1.0"
              className="text-primary-700 hover:underline"
            >
              [{dict.orders.duaLink} →]
            </a>
          </span>
        </label>
        {!agreed ? (
          <p className="mt-2 text-xs text-text-muted">
            {dict.orders.duaRequiredHint}
          </p>
        ) : null}
        {error ? (
          <div className="mt-3">
            <ErrorBanner
              code={error.code}
              requestId={error.requestId}
              detail={error.detail}
            />
          </div>
        ) : null}
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={placeOrder}
            disabled={!agreed || submitting || items.length === 0}
            data-testid="place-order"
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {submitting ? dict.orders.submitting : dict.orders.submitCta}
          </button>
          <Link
            href="/search"
            className="rounded-md border border-border px-4 py-2 text-sm text-text-muted hover:bg-bg-muted"
          >
            {dict.orders.backToSearch}
          </Link>
        </div>
      </section>
    </div>
  );
}

function SummaryRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-text">{children}</dd>
    </>
  );
}

/**
 * DistributionCard — stacked horizontal bar chart placeholder
 * (K-10 deferred — line-art donut shipped in v0.1.1). For v0.1 we render
 * a count + bar percent so the data is honest without a chart library.
 */
function DistributionCard({
  title,
  rows,
}: {
  title: string;
  rows: { key: string; count: number }[];
}) {
  const total = rows.reduce((sum, r) => sum + r.count, 0) || 1;
  return (
    <div className="rounded-md border border-border bg-bg p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
        {title}
      </h3>
      <ul className="flex flex-col gap-1.5 text-sm">
        {rows.map((r) => {
          const pct = Math.round((r.count / total) * 100);
          return (
            <li key={r.key} className="flex items-center gap-2">
              <span className="w-24 shrink-0 truncate font-mono text-xs text-text">
                {r.key}
              </span>
              <span
                aria-hidden
                className="h-2 rounded-pill bg-primary-600"
                style={{ width: `${pct}%`, minWidth: 4 }}
              />
              <span className="w-8 shrink-0 text-right font-mono text-xs tabular-nums text-text-muted">
                {r.count}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
