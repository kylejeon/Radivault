"use client";

/**
 * SearchAppV3 — dev-spec-buyer-search-v3 FR-V3-UI-1, integrating:
 *   <FacetSidebarV3>  (5 accordion groups)
 *   <ResultTable>     (13 columns, 9 sortable)
 *   <KCDAutocomplete> (triple-ontology dropdown)
 *   <TrustBar> / <PIPATrustNote>
 *
 * Wires:
 *   POST /api/search/studies   — main fetch with v3 filters + sort enums
 *   GET  /api/search/facets    — global facets (driven separately when no
 *                                 active filter)
 *   GET  /api/search/kcd-autocomplete?q= — typing dropdown
 *
 * Debounce: 250 ms on facet changes (FR-V3-UI-2 spec).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ErrorBanner } from "@/components/ErrorBanner";
import { FederatedSignal } from "@/components/buyer/FederatedSignal";
import {
  ColumnToggle,
  V3_COLUMN_DEFS,
  V3_DEFAULT_VISIBLE,
} from "@/components/buyer/v3/ColumnToggle";
import {
  EMPTY_V3_FACET_STATE,
  FacetSidebarV3,
  type FacetItem,
  type V3FacetState,
} from "@/components/buyer/v3/FacetSidebarV3";
import { KCDAutocomplete, type KCDItem } from "@/components/buyer/v3/KCDAutocomplete";
import {
  ResultTable,
  type ResultTableItem,
  type SortDir,
  type SortKey,
} from "@/components/buyer/v3/ResultTable";
import { SearchBar } from "@/components/buyer/v3/SearchBar";
import {
  KCDHeuristicNote,
  PIPATrustNote,
  TrustBar,
} from "@/components/buyer/v3/TrustBar";
import {
  LocaleProvider,
  LocaleToggle,
  useLocale,
} from "@/components/shared/LocaleToggle";
import type { Locale } from "@/lib/i18n";

type SearchResp = {
  items: ResultTableItem[];
  facets?: Record<string, FacetItem[]> | null;
  total_count?: number | null;
  total_hint?: number | null;
  next_cursor?: string | null;
  has_next?: boolean;
  meta?: {
    query_duration_ms?: number;
    buyer_tier?: string | null;
    // text-search-description FR-TS-2 / FR-TS-10 — additive fields used by the
    // search-bar surface. Both safe to read off the legacy facet-only path
    // because the executor always emits them (false / []).
    text_search_applied?: boolean;
    phi_flagged_patterns?: string[];
  } | null;
};

/**
 * v2 cohort sessionStorage shape — `/orders/new` (`OrderReviewClient`) reads
 * this key and renders `<CartItem variant="full">` rows from it. Keeping the
 * key + shape identical to v2 means the v3 search page can hand a federated
 * cohort to the legacy order-review flow without any contract change. This is
 * also what unblocks the `order-flow` playwright suite after the v3 swap.
 */
const COHORT_STORAGE_KEY = "radivault.cohort.v1";
type CohortItem = {
  pseudo_study_uid: string;
  modality: string | null;
  body_part: string | null;
  age_bucket: string | null;
  sex: string | null;
  total_bytes: number;
  hospital_opaque_id: string | null;
  study_date_shifted: string | null;
};
type CohortMap = Record<string, CohortItem>;

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

function saveCohort(c: CohortMap) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(COHORT_STORAGE_KEY, JSON.stringify(c));
  } catch {
    /* ignore quota */
  }
}

function toCohortItem(it: ResultTableItem): CohortItem {
  return {
    pseudo_study_uid: it.pseudo_study_uid,
    modality: it.modality,
    body_part: it.body_part,
    age_bucket: it.age_bucket,
    sex: it.sex,
    total_bytes: it.total_bytes,
    // ResultTableItem.hospital_opaque_id is non-nullable string; CartItemData
    // accepts string | null, so we keep the empty-string sentinel out.
    hospital_opaque_id: it.hospital_opaque_id || null,
    study_date_shifted: it.study_date_shifted,
  };
}

const SORT_TO_API: Record<string, string> = {
  "hospital:asc": "hospital_asc",
  "hospital:desc": "hospital_desc",
  "examdate:asc": "date_asc",
  "examdate:desc": "date_desc",
  "modality:asc": "modality_asc",
  "modality:desc": "modality_desc",
  "bodypart:asc": "body_part_asc",
  "bodypart:desc": "body_part_desc",
  "kcd:asc": "kcd_asc",
  "kcd:desc": "kcd_desc",
  "age:asc": "age_asc",
  "age:desc": "age_desc",
  "mfg:asc": "manufacturer_asc",
  "mfg:desc": "manufacturer_desc",
  "model:asc": "model_asc",
  "model:desc": "model_desc",
  "size:asc": "size_asc",
  "size:desc": "size_desc",
};

function buildSearchRequest(
  facets: V3FacetState,
  sortKey: SortKey,
  sortDir: SortDir,
  pageSize: number,
  qText: string,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    sort: SORT_TO_API[`${sortKey}:${sortDir}`] ?? "date_desc",
    limit: pageSize,
    include_facets: true,
  };
  // text-search-description FR-TS-2 — additive q field. Empty/whitespace is
  // dropped client-side too so the legacy /search payload shape is identical
  // to v3 facet-only when the buyer hasn't typed anything.
  if (qText.trim().length > 0) {
    body.q = qText.trim();
  }
  if (facets.modality.length) body.modality = facets.modality;
  if (facets.body_part.length) body.body_part = facets.body_part;
  if (facets.sex.length) body.sex = facets.sex;
  if (facets.manufacturer.length) body.manufacturer = facets.manufacturer;
  if (facets.kcd_code.length) body.kcd_code = facets.kcd_code;
  if (facets.hospital_region.length)
    body.hospital_region = facets.hospital_region;
  if (facets.age_min > 0) body.age_min = facets.age_min;
  if (facets.age_max < 120) body.age_max = facets.age_max;
  if (facets.year.length === 1) {
    const y = facets.year[0];
    body.study_date_shifted = { from: `${y}-01-01`, to: `${y}-12-31` };
  }
  return body;
}

export function SearchAppV3({ locale = "en" }: { locale?: Locale }) {
  // The outer wrapper installs <LocaleProvider> so every v3 child can call
  // useLocale() and react to runtime EN ↔ KR swap (QA HIGH-3 / BL-2). The
  // SSR-supplied `locale` prop seeds the initial value; localStorage / cookie
  // hydration happens inside the provider on mount.
  return (
    <LocaleProvider initial={locale === "ko" ? "ko" : "en"}>
      <SearchAppV3Inner />
    </LocaleProvider>
  );
}

function SearchAppV3Inner() {
  const { locale: lc } = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [facets, setFacets] = useState<V3FacetState>(EMPTY_V3_FACET_STATE);
  const [sortKey, setSortKey] = useState<SortKey>("examdate");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [pageSize, setPageSize] = useState(25);
  const [response, setResponse] = useState<SearchResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [kcdQuery, setKcdQuery] = useState("");
  // text-search-description FR-TS-1 — free-text search bar state. ``qText``
  // is the live, debounced input; ``qApplied`` is the value that has actually
  // been submitted (Enter / autocomplete pick) and is currently in the URL.
  // We split them so typing without submitting doesn't re-fetch on every
  // keystroke (autocomplete already covers that).
  const initialQ = (searchParams?.get("q") ?? "").slice(0, 200);
  const [qText, setQText] = useState(initialQ);
  const [qApplied, setQApplied] = useState(initialQ);
  const [visibleColumns, setVisibleColumns] = useState<string[]>(
    V3_DEFAULT_VISIBLE,
  );
  const [error, setError] = useState<{
    code?: string;
    detail?: string;
    requestId?: string;
  } | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Hydrate selection from sessionStorage on mount so toggling a row on
  // /search and then bouncing back from /orders/new keeps the cart visible.
  useEffect(() => {
    const cur = loadCohort();
    setSelected(new Set(Object.keys(cur)));
  }, []);

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      void runSearch();
    }, 250);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facets, sortKey, sortDir, pageSize, qApplied]);

  async function runSearch() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/search/studies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          buildSearchRequest(facets, sortKey, sortDir, pageSize, qApplied),
        ),
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
    } catch (err) {
      setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
    } finally {
      setLoading(false);
    }
  }

  // FR-TS-1 — push q into the URL so a /search?q=brain deep-link works.
  function commitQ(next: string) {
    const trimmed = next.trim();
    setQApplied(trimmed);
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    if (trimmed) params.set("q", trimmed);
    else params.delete("q");
    const qs = params.toString();
    router.replace(qs ? `/search?${qs}` : "/search");
  }

  const items = useMemo(() => response?.items ?? [], [response]);
  const facetData = (response?.facets ?? {}) as Record<string, FacetItem[]>;
  const total =
    response?.total_count ?? response?.total_hint ?? items.length;
  const queryMs = response?.meta?.query_duration_ms ?? 0;
  const distinctHospitals = new Set(
    items.map((it) => it.hospital_region_pseudo).filter(Boolean),
  ).size;

  function onSort(key: SortKey, dir: SortDir) {
    setSortKey(key);
    setSortDir(dir);
  }

  function toggleRow(uid: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      const cohort = loadCohort();
      if (next.has(uid)) {
        next.delete(uid);
        delete cohort[uid];
      } else {
        next.add(uid);
        const item = items.find((i) => i.pseudo_study_uid === uid);
        if (item) cohort[uid] = toCohortItem(item);
      }
      saveCohort(cohort);
      return next;
    });
  }

  function onKcdSelect(item: KCDItem) {
    if (facets.kcd_code.includes(item.code)) return;
    setFacets({ ...facets, kcd_code: [...facets.kcd_code, item.code] });
  }

  return (
    <div className="surface-buyer">
      {/* Top-bar trust pill row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "10px 24px",
          background: "var(--rv-navy-700)",
          color: "#ECECEC",
        }}
        data-testid="v3-trust-row"
      >
        <span style={{ fontWeight: 700, color: "#fff" }}>RadiVault</span>
        <TrustBar locale={lc} />
        <div style={{ marginLeft: "auto" }}>
          <LocaleToggle variant="dark" />
        </div>
      </div>

      {/* text-search-description FR-TS-1 — hero free-text search bar.
         Sits above the v3 sub-bar so it dominates the visual entry point
         without disturbing the 3-pane layout below. ``flag-off`` is honoured
         via NEXT_PUBLIC_TEXT_SEARCH_ENABLED — when explicitly "false" we
         unmount the bar so the legacy facet-only flow is byte-identical. */}
      {process.env.NEXT_PUBLIC_TEXT_SEARCH_ENABLED !== "false" ? (
        <div
          style={{
            padding: "20px 24px 12px",
            background: "#fff",
          }}
        >
          <SearchBar
            value={qText}
            onChange={setQText}
            onSubmit={(submitted) => {
              setQText(submitted);
              commitQ(submitted);
            }}
            locale={lc}
            flaggedPatterns={response?.meta?.phi_flagged_patterns ?? []}
          />
        </div>
      ) : null}

      {/* Sub-bar: KCD autocomplete + page size + sort summary */}
      <div
        style={{
          display: "flex",
          gap: 16,
          alignItems: "center",
          padding: "12px 24px",
          background: "#fff",
          borderBottom: "1px solid var(--rv-stone-200)",
        }}
      >
        <KCDAutocomplete
          value={kcdQuery}
          onChange={setKcdQuery}
          onSelect={onKcdSelect}
          locale={lc}
        />
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ fontSize: 12, color: "var(--rv-stone-500)" }}>
            {lc === "ko" ? "페이지" : "Page size"}
          </label>
          <select
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            style={{
              padding: "6px 10px",
              border: "1px solid var(--rv-stone-300)",
              borderRadius: 4,
              fontSize: 12,
            }}
            data-testid="v3-page-size"
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      {/* Main 2-col layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "var(--rv-sidebar-w) 1fr",
          minHeight: "calc(100vh - 200px)",
        }}
      >
        <FacetSidebarV3
          values={facets}
          onChange={setFacets}
          facets={facetData}
          resultCount={typeof total === "number" ? total : undefined}
          locale={lc}
        />
        <section style={{ padding: "16px 24px 80px" }}>
          {/* Results header */}
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              marginBottom: 12,
              paddingBottom: 10,
              borderBottom: "1px solid var(--rv-stone-200)",
            }}
            data-testid="v3-results-header"
          >
            <div>
              <span
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color: "var(--rv-navy-900)",
                  fontFamily: "JetBrains Mono, monospace",
                }}
              >
                {total}
              </span>
              <small
                style={{
                  marginLeft: 8,
                  fontSize: 12,
                  color: "var(--rv-stone-500)",
                }}
              >
                {lc === "ko"
                  ? `건 · 전체 PIPA 검증 완료 · ${distinctHospitals}개 병원 · ${queryMs} ms`
                  : `studies · all PIPA-verified · ${distinctHospitals} hospitals · ${queryMs} ms`}
              </small>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                color: "var(--rv-stone-500)",
              }}
            >
              <span>
                {lc === "ko"
                  ? `정렬: ${sortKey} ${sortDir === "desc" ? "↓" : "↑"}`
                  : `Sort: ${sortKey} ${sortDir === "desc" ? "↓" : "↑"}`}
              </span>
              <ColumnToggle
                columns={V3_COLUMN_DEFS}
                visibleKeys={visibleColumns}
                onChange={setVisibleColumns}
                locale={lc}
              />
            </div>
          </div>

          {/*
            v2 testid bridge — keeps `cohort-review-cta` and `federated-signal`
            available so the v0.2-buyer-data-access / order-flow / search-flow
            playwright suites continue to act as the BLOCKER #1/#2 regression
            safety net even after the /search route was swapped to <SearchAppV3>.
            The v3 visual layout is unchanged below — this row sits above the
            error banner in a compact container that mirrors the v2 sticky
            FederatedSignal placement.
          */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              marginBottom: 12,
            }}
          >
            <FederatedSignal
              studyCount={typeof total === "number" ? total : items.length}
              hospitalCount={distinctHospitals}
              variant="standard"
              locale={lc}
            />
            <Link
              href="/orders/new"
              data-testid="cohort-review-cta"
              aria-disabled={selected.size === 0}
              tabIndex={selected.size === 0 ? -1 : 0}
              onClick={(e) => {
                if (selected.size === 0) e.preventDefault();
              }}
              style={{
                whiteSpace: "nowrap",
                padding: "8px 14px",
                borderRadius: 4,
                fontSize: 12,
                fontWeight: 600,
                background:
                  selected.size === 0
                    ? "var(--rv-stone-200)"
                    : "var(--rv-navy-900)",
                color:
                  selected.size === 0 ? "var(--rv-stone-500)" : "#fff",
                textDecoration: "none",
              }}
            >
              {lc === "ko" ? "주문 검토" : "Review order"} ({selected.size})
            </Link>
          </div>

          {error ? (
            <ErrorBanner
              code={error.code}
              detail={error.detail}
              requestId={error.requestId}
            />
          ) : null}

          {loading && items.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--rv-stone-500)" }}>
              {lc === "ko" ? "로딩 중…" : "Loading…"}
            </div>
          ) : items.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--rv-stone-500)" }}>
              {lc === "ko"
                ? "조건에 맞는 결과가 없습니다."
                : "No studies match the current filter."}
            </div>
          ) : (
            <ResultTable
              items={items}
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={onSort}
              selected={selected}
              onToggleRow={toggleRow}
              locale={lc}
              visibleColumns={visibleColumns}
            />
          )}

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              marginTop: 14,
            }}
            data-testid="v3-footer-notes"
          >
            <PIPATrustNote locale={lc} />
            <KCDHeuristicNote locale={lc} />
          </div>
        </section>
      </div>
    </div>
  );
}
