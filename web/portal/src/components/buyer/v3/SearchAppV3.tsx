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

import { useEffect, useRef, useState } from "react";
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
} from "@/components/buyer/v3/TrustBar";
import { useLocale } from "@/components/shared/LocaleToggle";
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
  cursor: string | null,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    sort: SORT_TO_API[`${sortKey}:${sortDir}`] ?? "date_desc",
    limit: pageSize,
    // Skip facets on follow-up pages — facet counts are computed on the
    // FULL filtered set, so they're identical across pages and re-running
    // them just burns CPU on the search service.
    include_facets: cursor === null,
  };
  if (cursor) body.cursor = cursor;
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

/**
 * Top-level <SearchAppV3>. <LocaleProvider> now lives in /search/page.tsx
 * (so the marketplace top-bar's locale-toggle slot shares the same context),
 * and this export is just the inner client tree.
 *
 * `locale` prop kept for API compatibility — currently unused because the
 * inner reads `useLocale()` against the page-level provider.
 */
export function SearchAppV3({ locale: _locale = "en" }: { locale?: Locale }) {
  return <SearchAppV3Inner />;
}

// ---------------------------------------------------------------------------
// URL persistence (Kyle 2026-04-28) — facet state + sort + pageSize + free-
// text query are mirrored into ?modality=…&body_part=…&q=… on every change
// via router.replace, and hydrated from the same params on mount. Goal: the
// buyer's filters survive /search → /studies/[uid] → back navigation, and
// also survive a hard reload. Live typing (qText) is persisted too so the
// input box still has the partially-typed value after a navigation.
// ---------------------------------------------------------------------------
const LIST_KEYS: Array<keyof V3FacetState> = [
  "modality",
  "body_part",
  "sex",
  "manufacturer",
  "kcd_code",
  "hospital_region",
  "year",
];

function readListParam(
  params: ReturnType<typeof useSearchParams>,
  key: string,
): string[] {
  const v = params?.get(key);
  if (!v) return [];
  return v
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function hydrateFacetsFromUrl(
  params: ReturnType<typeof useSearchParams>,
): V3FacetState {
  if (!params) return EMPTY_V3_FACET_STATE;
  const ageMinRaw = Number(params.get("age_min"));
  const ageMaxRaw = Number(params.get("age_max"));
  return {
    modality: readListParam(params, "modality"),
    body_part: readListParam(params, "body_part"),
    sex: readListParam(params, "sex"),
    manufacturer: readListParam(params, "manufacturer"),
    kcd_code: readListParam(params, "kcd_code"),
    hospital_region: readListParam(params, "hospital_region"),
    year: readListParam(params, "year"),
    age_min: Number.isFinite(ageMinRaw) && ageMinRaw > 0 ? ageMinRaw : 0,
    age_max:
      Number.isFinite(ageMaxRaw) && ageMaxRaw > 0 && ageMaxRaw < 120
        ? ageMaxRaw
        : 120,
  };
}

function serializeStateToParams(args: {
  facets: V3FacetState;
  sortKey: SortKey;
  sortDir: SortDir;
  pageSize: number;
  qText: string;
}): URLSearchParams {
  const p = new URLSearchParams();
  if (args.qText.trim().length > 0) p.set("q", args.qText.trim());
  for (const key of LIST_KEYS) {
    const arr = args.facets[key] as string[];
    if (arr.length > 0) p.set(key, arr.join(","));
  }
  if (args.facets.age_min > 0) p.set("age_min", String(args.facets.age_min));
  if (args.facets.age_max < 120) p.set("age_max", String(args.facets.age_max));
  if (args.sortKey !== "examdate") p.set("sort", args.sortKey);
  if (args.sortDir !== "desc") p.set("dir", args.sortDir);
  if (args.pageSize !== 25) p.set("limit", String(args.pageSize));
  return p;
}

function SearchAppV3Inner() {
  const { locale: lc } = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [facets, setFacets] = useState<V3FacetState>(() =>
    hydrateFacetsFromUrl(searchParams),
  );
  const [sortKey, setSortKey] = useState<SortKey>(() => {
    const v = searchParams?.get("sort");
    return (v as SortKey) ?? "examdate";
  });
  const [sortDir, setSortDir] = useState<SortDir>(() => {
    const v = searchParams?.get("dir");
    return v === "asc" ? "asc" : "desc";
  });
  const [pageSize, setPageSize] = useState(() => {
    const v = Number(searchParams?.get("limit"));
    return v === 25 || v === 50 || v === 100 ? v : 25;
  });
  const [response, setResponse] = useState<SearchResp | null>(null);
  const [loading, setLoading] = useState(true);
  // Cursor pagination (Kyle 2026-04-27 — search showed 25/257 with no way
  // to reach the rest). Items accumulate across pages; cursor + facet
  // sha256 reset whenever a filter / sort / q change forces a fresh fetch.
  const [accumulatedItems, setAccumulatedItems] = useState<ResultTableItem[]>(
    [],
  );
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasNext, setHasNext] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  // Facet sidebar policy (Kyle 2026-04-27): the *option list* on the left
  // stays stable so checkboxes don't disappear when a filter narrows the
  // result set; only the *count* next to each option updates. Booking.com
  // / Amazon pattern.
  //
  //   currentFacets    = counts from the most recent fetch that included
  //                      facets (cursor pagination skips facets, so we
  //                      can't always read response.facets directly).
  //   unfilteredFacets = the canonical option list — a snapshot of facets
  //                      from a fetch where NO facet filters were active
  //                      (q can be present; q is a more fundamental scope
  //                      change, so unfilteredFacets refreshes when q
  //                      changes too).
  const [currentFacets, setCurrentFacets] = useState<
    Record<string, FacetItem[]>
  >({});
  const [unfilteredFacets, setUnfilteredFacets] = useState<
    Record<string, FacetItem[]> | null
  >(null);
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

  // IntersectionObserver — fires when the sentinel below the table scrolls
  // into view, triggering the next cursor fetch. Disabled while a fetch is
  // already in flight or when the upstream says there's no more data.
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;
    if (!hasNext || loading || loadingMore) return;
    const obs = new IntersectionObserver(
      (entries) => {
        const e = entries[0];
        if (e?.isIntersecting && hasNext && !loadingMore && !loading) {
          void runSearch({ append: true });
        }
      },
      { rootMargin: "300px 0px" },
    );
    obs.observe(node);
    return () => obs.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasNext, loading, loadingMore, nextCursor]);

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      void runSearch({ append: false });
    }, 250);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facets, sortKey, sortDir, pageSize, qApplied]);

  // URL persistence (Kyle 2026-04-28). Mirror live state into searchParams
  // via router.replace so back-nav from /studies/[uid] and hard reloads
  // both restore the buyer's filters + typed query. Skips work when the
  // serialised query string is identical to what's already in the URL.
  // ALSO writes to sessionStorage so the StudyDetailSubBar's "Back to
  // search" Link can rebuild this URL — that link uses an absolute
  // href="/search" which would otherwise strip the query.
  const urlSyncRef = useRef<string | null>(null);
  useEffect(() => {
    const params = serializeStateToParams({
      facets,
      sortKey,
      sortDir,
      pageSize,
      qText,
    });
    const qs = params.toString();
    if (urlSyncRef.current === qs) return;
    urlSyncRef.current = qs;
    const target = qs ? `/search?${qs}` : "/search";
    router.replace(target, { scroll: false });
    if (typeof window !== "undefined") {
      try {
        window.sessionStorage.setItem("radivault.lastSearchUrl", target);
      } catch {
        /* storage full / disabled — best-effort */
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facets, sortKey, sortDir, pageSize, qText]);

  async function runSearch(opts: { append: boolean }) {
    if (opts.append) setLoadingMore(true);
    else setLoading(true);
    setError(null);
    try {
      const cursorToSend = opts.append ? nextCursor : null;
      const res = await fetch("/api/search/studies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          buildSearchRequest(
            facets,
            sortKey,
            sortDir,
            pageSize,
            qApplied,
            cursorToSend,
          ),
        ),
      });
      if (res.status === 401) {
        router.push("/signin");
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        // ERR_CURSOR_FILTER_MISMATCH = filters changed under the cursor.
        // Drop the cursor and refetch from page 1 transparently.
        if (
          opts.append &&
          (body?.error === "ERR_CURSOR_FILTER_MISMATCH" ||
            body?.error === "ERR_CURSOR_INVALID")
        ) {
          setNextCursor(null);
          setAccumulatedItems([]);
          setHasNext(false);
          void runSearch({ append: false });
          return;
        }
        setError({
          code: body?.error,
          detail: body?.detail,
          requestId: body?.request_id,
        });
        if (!opts.append) {
          setResponse(null);
          setAccumulatedItems([]);
          setNextCursor(null);
          setHasNext(false);
        }
        return;
      }
      const data = (await res.json()) as SearchResp;
      setResponse(data);
      setNextCursor(data.next_cursor ?? null);
      setHasNext(Boolean(data.has_next));

      // Facet bookkeeping. Cursor pages return null (we skip facets after
      // page 1 to save CPU on the search service), so we only update when
      // the response actually carries facets.
      if (data.facets) {
        setCurrentFacets(data.facets);
        // Snapshot the option list whenever NO facet filter is applied —
        // this is "the world" for the current q. Used as the stable option
        // list for the sidebar even after the buyer applies a filter.
        const noFacetFiltersActive =
          facets.modality.length === 0 &&
          facets.body_part.length === 0 &&
          facets.sex.length === 0 &&
          facets.manufacturer.length === 0 &&
          facets.kcd_code.length === 0 &&
          facets.hospital_region.length === 0 &&
          facets.year.length === 0 &&
          facets.age_min === 0 &&
          facets.age_max === 120;
        if (noFacetFiltersActive && !opts.append) {
          setUnfilteredFacets(data.facets);
        }
      }

      const incoming = data.items ?? [];
      if (opts.append) {
        setAccumulatedItems((prev) => {
          // De-dupe by pseudo_study_uid (defensive — cursor pagination
          // shouldn't repeat, but a filter mismatch race could).
          const seen = new Set(prev.map((it) => it.pseudo_study_uid));
          const merged = [...prev];
          for (const it of incoming) {
            if (!seen.has(it.pseudo_study_uid)) merged.push(it);
          }
          return merged;
        });
      } else {
        setAccumulatedItems(incoming);
      }
    } catch (err) {
      setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
    } finally {
      if (opts.append) setLoadingMore(false);
      else setLoading(false);
    }
  }

  // FR-TS-1 — commit triggers a fetch via qApplied. URL persistence is
  // handled by the global state↔URL sync effect above (it watches qText),
  // so we don't double-write here.
  function commitQ(next: string) {
    setQApplied(next.trim());
  }

  // Items now come from the accumulator so cursor-paginated rows survive
  // across follow-up fetches (response only carries the latest page).
  const items = accumulatedItems;
  // Build the sidebar facet view: stable option list from `unfilteredFacets`,
  // counts from `currentFacets`. Items missing from currentFacets show 0 so
  // the buyer can see "no studies match" without the option vanishing.
  const facetData: Record<string, FacetItem[]> = (() => {
    if (!unfilteredFacets) return currentFacets;
    const merged: Record<string, FacetItem[]> = {};
    for (const [key, options] of Object.entries(unfilteredFacets)) {
      const cur = currentFacets[key] ?? [];
      const countByValue = new Map<string, number>();
      for (const it of cur) countByValue.set(String(it.value ?? ""), it.count);
      merged[key] = options.map((it) => ({
        value: it.value,
        count: countByValue.get(String(it.value ?? "")) ?? 0,
      }));
    }
    return merged;
  })();
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

  /**
   * Header-row "select all on this page" — adds the visible UIDs to the
   * selection set + cohort. Idempotent if some are already selected.
   */
  function selectAllVisible(uids: string[]) {
    setSelected((prev) => {
      const next = new Set(prev);
      const cohort = loadCohort();
      for (const uid of uids) {
        next.add(uid);
        const item = items.find((i) => i.pseudo_study_uid === uid);
        if (item) cohort[uid] = toCohortItem(item);
      }
      saveCohort(cohort);
      return next;
    });
  }

  /**
   * Header-row "clear" — wipes the WHOLE selection set + cohort. Per
   * Kyle 2026-04-27, this is the buyer's "reset everything I've done"
   * gesture, so we ALSO drop active facet filters + free-text query so
   * the result table snaps back to the 257-study canonical universe.
   *
   * Setting facets / qApplied triggers the 250 ms debounced search
   * effect → fresh fetch → resets cursor + accumulator transparently.
   */
  function clearAllSelection() {
    setSelected(new Set());
    saveCohort({});
    setFacets(EMPTY_V3_FACET_STATE);
    setQText("");
    commitQ("");
  }

  return (
    <div className="surface-buyer">
      {/*
        Trust pill + LocaleToggle previously rendered here in a separate navy
        strip (`v3-trust-row`); they're now slotted into <MarketplaceNav> so
        the page only ships ONE top bar (Kyle 2026-04-27 dedup). See
        web/portal/src/components/buyer/MarketplaceNavTrustSlots.tsx +
        /search/page.tsx where the slots are wired.
      */}

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
        {/* min-width: 0 lets this 1fr grid track shrink below its intrinsic
            content width, which is what allows the inner ResultTable wrapper
            to clamp to the viewport and own horizontal scroll on its own
            (instead of expanding the whole page right). */}
        <section style={{ padding: "16px 24px 80px", minWidth: 0 }}>
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
                gap: 12,
                fontSize: 12,
                color: "var(--rv-stone-500)",
              }}
            >
              <span>
                {lc === "ko"
                  ? `정렬: ${sortKey} ${sortDir === "desc" ? "↓" : "↑"}`
                  : `Sort: ${sortKey} ${sortDir === "desc" ? "↓" : "↑"}`}
              </span>
              {/* Page size moved out of the (now-removed) sub-bar so the
                  control density on this row matches Show columns / Sort
                  (Kyle 2026-04-27). */}
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <label
                  htmlFor="v3-page-size"
                  style={{ fontSize: 12, color: "var(--rv-stone-500)" }}
                >
                  {lc === "ko" ? "페이지" : "Page size"}
                </label>
                <select
                  id="v3-page-size"
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  style={{
                    padding: "5px 8px",
                    border: "1px solid var(--rv-stone-300)",
                    borderRadius: 4,
                    fontSize: 12,
                    background: "#fff",
                  }}
                  data-testid="v3-page-size"
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
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
            // Wrap the dense table in an overflow-x:auto container so when the
            // intrinsic min-width of all visible columns exceeds the section
            // width, only the table scrolls horizontally — the page itself
            // never gets a bottom scrollbar (Kyle 2026-04-27 feedback).
            <div style={{ overflowX: "auto", width: "100%" }}>
              <ResultTable
                items={items}
                sortKey={sortKey}
                sortDir={sortDir}
                onSort={onSort}
                selected={selected}
                onToggleRow={toggleRow}
                onSelectAllVisible={selectAllVisible}
                onClearAllSelection={clearAllSelection}
                locale={lc}
                visibleColumns={visibleColumns}
                query={qApplied}
              />
            </div>
          )}

          {/* Cursor pagination footer — auto-loads on scroll via the
              sentinel; the explicit button is the keyboard / a11y fallback
              and also prevents the IntersectionObserver from getting stuck
              when the viewport is already taller than the table. */}
          {items.length > 0 ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 12,
                padding: "16px 0 4px",
              }}
              data-testid="v3-pagination-footer"
            >
              <span
                style={{ fontSize: 12, color: "var(--rv-stone-500)" }}
                data-testid="v3-pagination-count"
              >
                {lc === "ko"
                  ? `${items.length} / ${typeof total === "number" ? total : items.length} 표시`
                  : `Showing ${items.length} of ${typeof total === "number" ? total : items.length}`}
              </span>
              {hasNext ? (
                <button
                  type="button"
                  onClick={() => void runSearch({ append: true })}
                  disabled={loadingMore}
                  data-testid="v3-load-more"
                  style={{
                    padding: "6px 14px",
                    background: loadingMore
                      ? "var(--rv-stone-200)"
                      : "var(--rv-navy-900)",
                    color: loadingMore ? "var(--rv-stone-500)" : "#fff",
                    border: "none",
                    borderRadius: 4,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: loadingMore ? "default" : "pointer",
                  }}
                >
                  {loadingMore
                    ? lc === "ko"
                      ? "로딩 중…"
                      : "Loading…"
                    : lc === "ko"
                      ? "더 보기"
                      : "Load more"}
                </button>
              ) : null}
              <div
                ref={sentinelRef}
                aria-hidden
                data-testid="v3-pagination-sentinel"
                style={{ width: 1, height: 1 }}
              />
            </div>
          ) : null}

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              marginTop: 14,
            }}
            data-testid="v3-footer-notes"
          >
            {/* PIPATrustNote removed (Kyle 2026-04-28) — buyer doesn't need
                PIPA §28-8 / 정통망법 boilerplate on every page. */}
            <KCDHeuristicNote locale={lc} />
          </div>
        </section>
      </div>
    </div>
  );
}
