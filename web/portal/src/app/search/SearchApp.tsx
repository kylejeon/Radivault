"use client";

/**
 * SearchApp — design-spec-portal-redesign §12.1 / FR-BP-3.
 *
 * 3-pane layout (desktop ≥ 1280 px target):
 *   [FacetSidebar 280 px] [Results flex-1 + FederatedSignal sticky] [Cohort 320 px]
 *
 * Search payload uses the canonical `SearchRequest` schema
 * (dev-spec-metadata-index §6.4): modality, body_part, age_bucket, sex,
 * study_date_shifted, manufacturer, min_hospitals, sort, limit, cursor,
 * include_facets. The FR-INF-8/9 cleanup retires the legacy
 * `{ page_size, modalities, body_parts }` shape.
 *
 * Cohort state is local-only (sessionStorage) — the v0.1 backend has no
 * "saved cohort" notion; an order is created from the in-memory selection.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ErrorBanner } from "@/components/ErrorBanner";
import { FederatedSignal } from "@/components/buyer/FederatedSignal";
import {
  EMPTY_FACET_STATE,
  FacetSidebar,
  type FacetState,
} from "@/components/buyer/FacetSidebar";
import { StudyCard, type StudyCardItem } from "@/components/buyer/StudyCard";
import { CartEmpty, CartItem, type CartItemData } from "@/components/buyer/CartItem";
import { getDict, type Locale } from "@/lib/i18n";

type FacetValue = { value: string; count: number };

type SearchResp = {
  items: SearchStudy[];
  facets?: Record<string, FacetValue[]> | null;
  total_count?: number | null;
  total_hint?: number | null;
  total_count_exact?: boolean;
  next_cursor?: string | null;
  has_next?: boolean;
  page_size?: number;
  response_truncated?: boolean;
};

type SearchStudy = StudyCardItem & CartItemData;

const COHORT_STORAGE_KEY = "radivault.cohort.v1";
const RECENT_KEY = "radivault.recentSearches.v1";

function loadCohort(): Record<string, SearchStudy> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(COHORT_STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, SearchStudy>;
  } catch {
    return {};
  }
}

function saveCohort(cohort: Record<string, SearchStudy>) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(COHORT_STORAGE_KEY, JSON.stringify(cohort));
  } catch {
    /* ignore quota */
  }
}

function loadRecent(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as string[];
  } catch {
    return [];
  }
}

function pushRecent(label: string) {
  if (typeof window === "undefined") return;
  if (!label.trim()) return;
  try {
    const cur = loadRecent();
    const next = [label, ...cur.filter((c) => c !== label)].slice(0, 5);
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
}

function buildSearchRequest(facets: FacetState, cursor?: string | null) {
  const body: Record<string, unknown> = {
    sort: "date_desc",
    limit: 25,
    include_facets: true,
  };
  if (facets.modality.length > 0) body.modality = facets.modality;
  if (facets.body_part.length > 0) body.body_part = facets.body_part;
  if (facets.age_bucket.length > 0) body.age_bucket = facets.age_bucket;
  if (facets.sex.length > 0) body.sex = facets.sex;
  if (facets.manufacturer.length > 0) body.manufacturer = facets.manufacturer;
  if (facets.min_hospitals > 1) body.min_hospitals = facets.min_hospitals;
  // year is a derived facet (EXTRACT YEAR FROM study_date_shifted) — for v0.1
  // we send the whole-year range when a single year is selected.
  if (facets.year.length === 1) {
    const y = facets.year[0];
    body.study_date_shifted = { from: `${y}-01-01`, to: `${y}-12-31` };
  }
  if (cursor) body.cursor = cursor;
  return body;
}

function chipLabel(facets: FacetState): string[] {
  const chips: string[] = [];
  if (facets.modality.length) chips.push(facets.modality.join("/"));
  if (facets.body_part.length) chips.push(facets.body_part.join("/"));
  if (facets.age_bucket.length) chips.push(facets.age_bucket.join("/"));
  if (facets.sex.length) chips.push(facets.sex.join("/"));
  if (facets.manufacturer.length) chips.push(facets.manufacturer.join("/"));
  if (facets.year.length) chips.push(facets.year.join("/"));
  if (facets.min_hospitals > 1)
    chips.push(`hospitals ≥ ${facets.min_hospitals}`);
  return chips;
}

function countDistinctHospitals(items: SearchStudy[]): number {
  const set = new Set<string>();
  for (const it of items) {
    if (it.hospital_opaque_id) set.add(it.hospital_opaque_id);
  }
  return set.size;
}

export function SearchApp({ locale = "en" }: { locale?: Locale }) {
  const dict = getDict(locale);
  const router = useRouter();
  const [facetValues, setFacetValues] = useState<FacetState>(EMPTY_FACET_STATE);
  const [response, setResponse] = useState<SearchResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{
    code?: string;
    detail?: string;
    requestId?: string;
  } | null>(null);
  const [cohort, setCohort] = useState<Record<string, SearchStudy>>(() =>
    loadCohort(),
  );
  const [recent, setRecent] = useState<string[]>(() => loadRecent());
  const [selectedUid, setSelectedUid] = useState<string | null>(null);

  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Persist cohort on every change.
  useEffect(() => {
    saveCohort(cohort);
  }, [cohort]);

  // Initial + facet-change fetch (debounced 300 ms per design-spec §11.5).
  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      void runSearch();
    }, 300);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facetValues]);

  async function runSearch() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/search/studies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildSearchRequest(facetValues)),
      });
      if (res.status === 401) {
        router.push("/signin");
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError({
          code: body?.error,
          detail: body?.detail,
          requestId: body?.request_id,
        });
        setResponse(null);
        return;
      }
      const data = (await res.json()) as SearchResp;
      setResponse(data);
      // Push a recent-search label only if a meaningful filter is active.
      const chips = chipLabel(facetValues);
      if (chips.length > 0) {
        const label = chips.slice(0, 3).join(" · ");
        pushRecent(label);
        setRecent(loadRecent());
      }
    } catch (err) {
      setError({
        code: "ERR_UPSTREAM_UNAVAILABLE",
        detail: String(err),
      });
    } finally {
      setLoading(false);
    }
  }

  const items = useMemo(() => response?.items ?? [], [response]);
  const total =
    response?.total_count ?? response?.total_hint ?? items.length;
  const hospitalCount = useMemo(() => countDistinctHospitals(items), [items]);
  const facets = (response?.facets ?? {}) as Record<string, FacetValue[]>;
  const cohortList = useMemo(() => Object.values(cohort), [cohort]);
  const cohortHospitals = useMemo(
    () => countDistinctHospitals(cohortList),
    [cohortList],
  );
  const cohortBytes = useMemo(
    () => cohortList.reduce((sum, s) => sum + s.total_bytes, 0),
    [cohortList],
  );

  function toggleStudy(study: SearchStudy) {
    setCohort((prev) => {
      const next = { ...prev };
      if (next[study.pseudo_study_uid]) {
        delete next[study.pseudo_study_uid];
      } else {
        next[study.pseudo_study_uid] = study;
      }
      return next;
    });
  }

  return (
    <div className="grid grid-cols-1 gap-0 desktop:grid-cols-[280px_minmax(0,1fr)_320px]">
      {/* Mobile fallback (K-9 deferred) */}
      <div className="desktop:hidden col-span-full p-6 text-sm text-text-muted">
        {dict.account.mobileFallbackTitle} —{" "}
        {dict.account.mobileFallbackBody}
      </div>

      {/* Left: facets */}
      <div className="hidden desktop:block">
        <FacetSidebar
          values={facetValues}
          onChange={setFacetValues}
          facets={{
            modality: facets.modality,
            body_part: facets.body_part,
            age_bucket: facets.age_bucket,
            sex: facets.sex,
            manufacturer: facets.manufacturer,
            year: facets.year,
          }}
          recentSearches={recent}
          onSelectRecent={() => {
            // v0.1 just clears facets — full restore lives in v0.1.1.
            setFacetValues(EMPTY_FACET_STATE);
          }}
          locale={locale}
        />
      </div>

      {/* Center: results */}
      <div className="hidden flex-col gap-3 px-4 py-4 desktop:flex">
        <FederatedSignal
          studyCount={typeof total === "number" ? total : items.length}
          hospitalCount={hospitalCount}
          filterChips={chipLabel(facetValues)}
          variant={items.length === 0 && !loading ? "empty" : "standard"}
          locale={locale}
        />
        {error ? (
          <ErrorBanner
            code={error.code}
            requestId={error.requestId}
            detail={error.detail}
          />
        ) : null}
        <div
          role="table"
          aria-label={dict.search.pageTitle}
          aria-busy={loading}
          className="rounded-md border border-border bg-bg"
        >
          {loading && items.length === 0 ? (
            <SkeletonRows />
          ) : items.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-text-muted">
              <div className="mb-2 font-medium text-text">
                {dict.search.emptyTitle}
              </div>
              <p>{dict.search.emptyBody}</p>
            </div>
          ) : (
            items.map((s) => (
              <StudyCard
                key={s.pseudo_study_uid}
                study={s}
                selected={Boolean(cohort[s.pseudo_study_uid])}
                onToggle={() => {
                  toggleStudy(s);
                  setSelectedUid(s.pseudo_study_uid);
                }}
                locale={locale}
              />
            ))
          )}
        </div>
        {response?.has_next ? (
          <button
            type="button"
            disabled
            className="self-center rounded-md border border-border px-4 py-2 text-sm text-text-muted"
            title="Pagination v0.1.1"
          >
            {dict.search.loadMore}
          </button>
        ) : null}
      </div>

      {/* Right: cohort sidebar */}
      <aside
        aria-label={dict.search.cohortTitle}
        className="hidden flex-col gap-3 border-l border-border bg-bg p-4 desktop:flex"
      >
        <h2 className="text-sm font-semibold text-text">
          {dict.search.cohortTitle}
        </h2>
        <FederatedSignal
          studyCount={cohortList.length}
          hospitalCount={cohortHospitals}
          variant="mini"
          locale={locale}
        />
        {cohortList.length === 0 ? (
          <CartEmpty locale={locale} />
        ) : (
          <div className="flex flex-col">
            {cohortList.map((s) => (
              <CartItem
                key={s.pseudo_study_uid}
                item={s}
                variant="mini"
                onRemove={() => toggleStudy(s)}
                locale={locale}
              />
            ))}
          </div>
        )}
        <div className="mt-2 text-xs text-text-muted">
          {dict.orders.summaryTotalSize}:{" "}
          <span className="font-mono">
            {(cohortBytes / (1024 * 1024)).toFixed(1)} MB
          </span>
        </div>
        <Link
          href="/orders/new"
          aria-disabled={cohortList.length === 0}
          tabIndex={cohortList.length === 0 ? -1 : 0}
          data-testid="cohort-review-cta"
          className={
            cohortList.length === 0
              ? "rounded-md bg-bg-muted px-3 py-2 text-center text-sm font-medium text-text-muted"
              : "rounded-md bg-primary-600 px-3 py-2 text-center text-sm font-semibold text-white hover:bg-primary-700"
          }
          onClick={(e) => {
            if (cohortList.length === 0) e.preventDefault();
          }}
        >
          {dict.search.cohortReviewCta} ({cohortList.length})
        </Link>
        {/* Quiet keep-warm marker so eslint doesn't whine about unused state. */}
        {selectedUid ? null : null}
      </aside>
    </div>
  );
}

function SkeletonRows() {
  return (
    <div className="flex flex-col">
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="h-14 animate-pulse border-b border-border last:border-b-0"
        />
      ))}
    </div>
  );
}
