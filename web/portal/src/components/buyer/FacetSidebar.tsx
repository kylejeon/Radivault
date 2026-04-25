"use client";

import { useState } from "react";
import clsx from "clsx";

/**
 * FacetSidebar {#facet-sidebar-v1} — design-spec-portal-redesign §11.5.
 * FR-BP-3 (left pane), FR-BP-7.
 *
 * Order (top→bottom): min_hospitals slider · modality · body_part · age_bucket ·
 * sex · manufacturer · year. min_hospitals is RadiVault's federated northstar
 * facet (FR-BP-7) and intentionally lives at the very top.
 *
 * Each facet section can be collapsed independently. Selection changes are
 * propagated immediately via `onChange` — debouncing is the page's
 * responsibility (the parent already debounces /api/search/studies calls).
 */

export type FacetItem = { value: string; count: number };

export type FacetState = {
  modality: string[];
  body_part: string[];
  age_bucket: string[];
  sex: string[];
  manufacturer: string[];
  year: string[];
  min_hospitals: number;
};

export const EMPTY_FACET_STATE: FacetState = {
  modality: [],
  body_part: [],
  age_bucket: [],
  sex: [],
  manufacturer: [],
  year: [],
  min_hospitals: 1,
};

export type FacetSidebarProps = {
  values: FacetState;
  onChange: (next: FacetState) => void;
  facets: {
    modality?: FacetItem[];
    body_part?: FacetItem[];
    age_bucket?: FacetItem[];
    sex?: FacetItem[];
    manufacturer?: FacetItem[];
    year?: FacetItem[];
  };
  /** Recent searches list (FR-BP-15, optional). */
  recentSearches?: string[];
  onSelectRecent?: (label: string) => void;
  locale?: "en" | "ko";
};

export function FacetSidebar({
  values,
  onChange,
  facets,
  recentSearches,
  onSelectRecent,
  locale = "en",
}: FacetSidebarProps) {
  const t =
    locale === "ko"
      ? {
          recent: "최근 검색",
          minHospitals: "최소 N 개 병원에 분포",
          modality: "모달리티",
          bodyPart: "신체 부위",
          age: "연령",
          sex: "성별",
          manufacturer: "제조사",
          year: "촬영 연도",
          clear: "필터 모두 해제",
          noFacets: "현재 결과에 값 없음.",
        }
      : {
          recent: "Recent searches",
          minHospitals: "Federated across at least N hospitals",
          modality: "Modality",
          bodyPart: "Body part",
          age: "Age bucket",
          sex: "Sex",
          manufacturer: "Manufacturer",
          year: "Year",
          clear: "Clear all filters",
          noFacets: "No values in current results.",
        };

  function toggle(key: keyof Omit<FacetState, "min_hospitals">, v: string) {
    const cur = new Set(values[key]);
    if (cur.has(v)) cur.delete(v);
    else cur.add(v);
    onChange({ ...values, [key]: Array.from(cur) });
  }

  function clearAll() {
    onChange(EMPTY_FACET_STATE);
  }

  const hasAny =
    values.modality.length > 0 ||
    values.body_part.length > 0 ||
    values.age_bucket.length > 0 ||
    values.sex.length > 0 ||
    values.manufacturer.length > 0 ||
    values.year.length > 0 ||
    values.min_hospitals !== 1;

  return (
    <aside
      data-testid="facet-sidebar"
      aria-label={locale === "ko" ? "필터" : "Filters"}
      className="flex w-full flex-col gap-4 border-r border-border bg-bg p-4"
    >
      {recentSearches && recentSearches.length > 0 ? (
        <FacetSection title={t.recent} testId="facet-recent">
          <ul className="flex flex-col gap-1 text-sm">
            {recentSearches.slice(0, 5).map((label) => (
              <li key={label}>
                <button
                  type="button"
                  onClick={() => onSelectRecent?.(label)}
                  className="truncate text-text-muted hover:text-primary-700 hover:underline"
                >
                  • {label}
                </button>
              </li>
            ))}
          </ul>
        </FacetSection>
      ) : null}

      {/* min_hospitals slider — FR-BP-7 lead facet. */}
      <FacetSection title={t.minHospitals} testId="facet-min-hospitals">
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={1}
            max={20}
            value={values.min_hospitals}
            onChange={(e) =>
              onChange({
                ...values,
                min_hospitals: Number.parseInt(e.target.value, 10),
              })
            }
            aria-label={t.minHospitals}
            className="flex-1 accent-primary-600"
          />
          <span
            data-testid="min-hospitals-value"
            className="w-8 text-right font-mono text-sm tabular-nums text-text"
          >
            {values.min_hospitals}+
          </span>
        </div>
      </FacetSection>

      <FacetMulti
        title={t.modality}
        testId="modality"
        items={facets.modality ?? []}
        selected={values.modality}
        onToggle={(v) => toggle("modality", v)}
        empty={t.noFacets}
      />
      <FacetMulti
        title={t.bodyPart}
        testId="body-part"
        items={facets.body_part ?? []}
        selected={values.body_part}
        onToggle={(v) => toggle("body_part", v)}
        empty={t.noFacets}
      />
      <FacetMulti
        title={t.age}
        testId="age-bucket"
        items={facets.age_bucket ?? []}
        selected={values.age_bucket}
        onToggle={(v) => toggle("age_bucket", v)}
        empty={t.noFacets}
      />
      <FacetSection title={t.sex} testId="facet-sex">
        <ul className="flex flex-col gap-1 text-sm">
          {(facets.sex ?? []).length === 0 ? (
            <li className="text-xs text-text-muted">{t.noFacets}</li>
          ) : null}
          {(facets.sex ?? []).map((it) => (
            <li key={`sex:${it.value}`}>
              <label className="flex items-center justify-between gap-2 text-sm">
                <span className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="facet-sex"
                    checked={values.sex[0] === it.value}
                    onChange={() =>
                      onChange({ ...values, sex: [it.value] })
                    }
                    className="size-4"
                  />
                  <span>{it.value}</span>
                </span>
                <FacetCount n={it.count} />
              </label>
            </li>
          ))}
        </ul>
      </FacetSection>
      <FacetMulti
        title={t.manufacturer}
        testId="manufacturer"
        items={facets.manufacturer ?? []}
        selected={values.manufacturer}
        onToggle={(v) => toggle("manufacturer", v)}
        empty={t.noFacets}
      />
      <FacetMulti
        title={t.year}
        testId="year"
        items={facets.year ?? []}
        selected={values.year}
        onToggle={(v) => toggle("year", v)}
        empty={t.noFacets}
      />

      {hasAny ? (
        <button
          type="button"
          onClick={clearAll}
          data-testid="facet-clear-all"
          className="self-start rounded-sm px-2 py-1 text-xs text-primary-700 hover:bg-bg-muted hover:underline"
        >
          {t.clear}
        </button>
      ) : null}
    </aside>
  );
}

function FacetSection({
  title,
  testId,
  children,
}: {
  title: string;
  testId: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <fieldset
      data-testid={`facet-section-${testId}`}
      className="border-b border-border pb-3 last:border-b-0"
    >
      <legend className="mb-2 flex w-full items-center justify-between gap-2 text-sm font-semibold text-text">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between gap-2 text-left"
          aria-expanded={open}
        >
          <span>{title}</span>
          <span aria-hidden className="text-text-muted">
            {open ? "▾" : "▸"}
          </span>
        </button>
      </legend>
      {open ? children : null}
    </fieldset>
  );
}

function FacetMulti({
  title,
  testId,
  items,
  selected,
  onToggle,
  empty,
}: {
  title: string;
  testId: string;
  items: FacetItem[];
  selected: string[];
  onToggle: (value: string) => void;
  empty: string;
}) {
  return (
    <FacetSection title={title} testId={testId}>
      <ul className="flex flex-col gap-1 text-sm">
        {items.length === 0 ? (
          <li className="text-xs text-text-muted">{empty}</li>
        ) : null}
        {items.map((it) => (
          <li key={`${testId}:${it.value}`}>
            <label className="flex cursor-pointer items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selected.includes(it.value)}
                  onChange={() => onToggle(it.value)}
                  className="size-4"
                />
                <span
                  className={clsx(
                    selected.includes(it.value) && "font-semibold",
                  )}
                >
                  {it.value || "(unknown)"}
                </span>
              </span>
              <FacetCount n={it.count} />
            </label>
          </li>
        ))}
      </ul>
    </FacetSection>
  );
}

function FacetCount({ n }: { n: number }) {
  return (
    <span className="rounded-pill bg-bg-muted px-2 py-0.5 text-[11px] tabular-nums text-text-muted">
      {n.toLocaleString()}
    </span>
  );
}
