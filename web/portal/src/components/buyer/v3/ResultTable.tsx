"use client";

/**
 * <ResultTable> — buyer-search-v3 FR-V3-UI-1.
 *
 * Dense 13-column table (16 grid tracks: stripe + check + 13 data + action).
 * Column order matches mockup `search.html` v3.2:
 *   stripe · check · Hospital · Exam Date · Modality · BodyPart · KCD ·
 *   Sex · Age · Manufacturer · Model · Sr·Inst · Size · UID · View
 *
 * Sortable headers click `onSort(sortKey)` with the next direction baked in
 * (the parent owns the active sort state). 9 sortable columns:
 *   hospital, examdate, modality, bodypart, kcd, age, mfg, model, size.
 */

import { useMemo } from "react";
import Link from "next/link";
import { HighlightedText } from "./HighlightedText";
import { HospitalBadge } from "./HospitalBadge";
import { KCDChip } from "./KCDChip";
import { ModalityDot } from "./ModalityDot";
import { PhiPendingBadge } from "./PhiPendingBadge";
import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";

export type ResultTableItem = {
  pseudo_study_uid: string;
  modality: string | null;
  body_part: string | null;
  sex: string | null;
  patient_age: number | null;
  age_bucket: string | null;
  study_date_shifted: string | null;
  manufacturer: string | null;
  model_name: string | null;
  n_instances: number;
  n_series: number;
  total_bytes: number;
  hospital_region_pseudo: string | null;
  hospital_opaque_id: string;
  kcd_code: string | null;
  kcd_label_ko: string | null;
  kcd_label_en: string | null;
  // text-search-description FR-TS-9 — server ts_headline result, null when
  // q is unused (legacy facet-only path).
  highlight_snippet?: string | null;
  // text-search-description Phase 1.5 (FR-TS15-6) — scrubbed description
  // text. NULL when feature flag off or pre-Phase-1.5 ingest; "" when
  // scrubbed-but-empty (PhiPendingBadge fallback).
  study_description?: string | null;
  protocol_name?: string | null;
};

export type SortDir = "asc" | "desc";
export type SortKey =
  | "hospital"
  | "examdate"
  | "modality"
  | "bodypart"
  | "kcd"
  | "age"
  | "mfg"
  | "model"
  | "size";

const SORTABLE: SortKey[] = [
  "hospital",
  "examdate",
  "modality",
  "bodypart",
  "kcd",
  "age",
  "mfg",
  "model",
  "size",
];

export type ResultTableProps = {
  items: ResultTableItem[];
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey, dir: SortDir) => void;
  selected?: Set<string>;
  onToggleRow?: (uid: string) => void;
  locale?: "ko" | "en";
  /**
   * Subset of <ColumnToggle>'s 12 toggleable column keys to render. Always-on
   * `hospital` is forced on regardless. `undefined` (legacy) → render all.
   * QA HIGH-2 / BL-1 wiring.
   */
  visibleColumns?: string[];
  /**
   * Active free-text query string (raw, pre-tsquery). Drives <HighlightedText>
   * so prefix matches like "bra" mark BRA inside BRAIN — see HighlightedText
   * docstring + Kyle's UX rule.
   */
  query?: string | null;
};

function L(locale: "ko" | "en", ko: string, en: string): string {
  return locale === "ko" ? ko : en;
}

function fmtBytes(b: number): string {
  if (b >= 1024 * 1024 * 1024) return `${(b / (1024 ** 3)).toFixed(1)} GB`;
  if (b >= 1024 * 1024) return `${Math.round(b / (1024 ** 2))} MB`;
  if (b >= 1024) return `${Math.round(b / 1024)} KB`;
  return `${b} B`;
}

function uidTail(u: string): string {
  if (!u) return "—";
  return `…${u.slice(-4)}`;
}

// CSS grid track definitions in mockup order (must match `globals.css`
// `.rv-result-table__row` template). Two leading fixed tracks (stripe +
// checkbox) are always rendered; data tracks are toggled per visibleColumns.
const TRACK_BY_COL: Record<string, string> = {
  hospital: "96px",
  examdate: "90px",
  modality: "72px",
  bodypart: "96px",
  // KCD column — wider min so "ICD-10 Z00.0 Generic..." doesn't ellipsis
  // immediately, and fr factor so it absorbs leftover horizontal space.
  kcd: "minmax(200px, 1.6fr)",
  sex: "36px",
  age: "44px",
  mfg: "110px",
  model: "120px",
  series: "76px",
  size: "72px",
  uid: "60px",
  // text-search-description Phase 1.5 (design-spec §8.1) — DESCRIPTION column
  // promoted to fr so it co-absorbs slack with KCD, eliminating the right-side
  // gap Kyle flagged on 1700px monitors.
  description: "minmax(200px, 1.4fr)",
  // trailing action column — width 64px
};

const ALL_COL_ORDER: string[] = [
  "hospital",
  "examdate",
  "modality",
  "bodypart",
  "kcd",
  "sex",
  "age",
  "mfg",
  "model",
  "series",
  "size",
  "description",
  "uid",
];

export function ResultTable({
  items,
  sortKey,
  sortDir,
  onSort,
  selected,
  onToggleRow,
  locale = "en",
  visibleColumns,
  query,
}: ResultTableProps) {
  // `hospital` always rendered (matches ColumnToggle "always" hint).
  const isCol = (key: string): boolean => {
    if (!visibleColumns) return true;
    if (key === "hospital") return true;
    return visibleColumns.includes(key);
  };

  // Build dynamic grid template that drops tracks for hidden columns so the
  // table doesn't leave gap whitespace. Stripe + checkbox + (visible data
  // columns) + trailing action.
  const gridTemplate = useMemo(() => {
    const tracks = ["var(--rv-col-stripe-w)", "32px"]; // stripe + check
    for (const key of ALL_COL_ORDER) {
      if (isCol(key)) tracks.push(TRACK_BY_COL[key]);
    }
    tracks.push("64px"); // action
    return tracks.join(" ");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleColumns]);
  const rowStyle: React.CSSProperties = visibleColumns
    ? { gridTemplateColumns: gridTemplate }
    : {};
  function header(key: SortKey, ko: string, en: string) {
    const isActive = sortKey === key;
    const nextDir: SortDir = isActive && sortDir === "desc" ? "asc" : "desc";
    return (
      <div
        role="columnheader"
        tabIndex={0}
        className="rv-col"
        data-sort={key}
        aria-sort={
          isActive ? (sortDir === "asc" ? "ascending" : "descending") : "none"
        }
        onClick={() => onSort(key, nextDir)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSort(key, nextDir);
          }
        }}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          color: "var(--rv-stone-500)",
          textTransform: "uppercase",
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.05em",
          cursor: "pointer",
          padding: "6px 10px",
        }}
      >
        <span>{L(locale, ko, en)}</span>
        <span aria-hidden style={{ opacity: isActive ? 1 : 0.35, fontSize: 9 }}>
          {isActive ? (sortDir === "asc" ? "▲" : "▼") : "▼"}
        </span>
      </div>
    );
  }

  function staticHead(ko: string, en: string) {
    return (
      <div className="rv-col" style={{ textTransform: "uppercase", fontSize: 11, fontWeight: 700, color: "var(--rv-stone-500)" }}>
        {L(locale, ko, en)}
      </div>
    );
  }

  return (
    <div
      role="table"
      aria-label="search results"
      data-testid="v3-result-table"
      className="rv-result-table"
    >
      <div
        className="rv-result-table__row rv-result-table__row--head"
        role="row"
        style={rowStyle}
      >
        <div className="rv-col-stripe" />
        <div className="rv-col rv-col-check" />
        {isCol("hospital") && header("hospital", "병원", "Hospital")}
        {isCol("examdate") && header("examdate", "촬영일", "Exam Date")}
        {isCol("modality") && header("modality", "모달리티", "Modality")}
        {isCol("bodypart") && header("bodypart", "부위", "BodyPart")}
        {isCol("kcd") && header("kcd", "KCD-8", "ICD-10")}
        {isCol("sex") && staticHead("성별", "Sex")}
        {isCol("age") && header("age", "나이", "Age")}
        {isCol("mfg") && header("mfg", "제조사", "Manufacturer")}
        {isCol("model") && header("model", "모델", "Model")}
        {isCol("series") && staticHead("Sr·Inst", "Sr · Inst")}
        {isCol("size") && header("size", "용량", "Size")}
        {isCol("description") && staticHead("검사 설명", "Description")}
        {isCol("uid") && staticHead("UID", "UID")}
        <div className="rv-col" />
      </div>

      {items.map((it) => {
        const region = it.hospital_region_pseudo;
        const isSelected = selected?.has(it.pseudo_study_uid) ?? false;
        return (
          <div
            key={it.pseudo_study_uid}
            role="row"
            data-testid="v3-row"
            data-uid={it.pseudo_study_uid}
            className="rv-result-table__row"
            style={rowStyle}
          >
            <HospitalBadge regionPseudo={region} variant="dot" />
            <div className="rv-col rv-col-check">
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggleRow?.(it.pseudo_study_uid)}
                aria-label={`select study ${it.pseudo_study_uid.slice(-6)}`}
              />
            </div>
            {isCol("hospital") && (
              <div className="rv-col">
                <HospitalBadge regionPseudo={region} query={query} />
              </div>
            )}
            {isCol("examdate") && (
              <div className="rv-col rv-col-mono">
                {it.study_date_shifted ?? "—"}
              </div>
            )}
            {isCol("modality") && (
              <div className="rv-col" style={{ display: "flex", alignItems: "center" }}>
                <ModalityDot modality={it.modality} query={query} />
              </div>
            )}
            {isCol("bodypart") && (
              <div className="rv-col" style={{ textTransform: "uppercase", fontWeight: 500, fontSize: 12 }}>
                {query ? (
                  <HighlightedText
                    html={it.highlight_snippet}
                    fallback={it.body_part ?? "—"}
                    query={query}
                    maxLength={32}
                  />
                ) : (
                  it.body_part ?? "—"
                )}
              </div>
            )}
            {isCol("kcd") && (
              <div className="rv-col rv-col-kcd">
                {it.kcd_code ? (
                  <KCDChip
                    code={it.kcd_code}
                    labelKo={it.kcd_label_ko}
                    labelEn={it.kcd_label_en}
                    locale={locale}
                    variant="inline"
                    size="md"
                  />
                ) : (
                  <span style={{ color: "var(--rv-stone-400)" }}>—</span>
                )}
              </div>
            )}
            {isCol("sex") && (
              <div className="rv-col" style={{ textAlign: "center", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5, fontWeight: 700, color: "var(--rv-navy-900)" }}>
                {it.sex ?? "—"}
              </div>
            )}
            {isCol("age") && (
              <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5, fontWeight: 600 }}>
                {it.patient_age ?? "—"}
              </div>
            )}
            {isCol("mfg") && (
              <div className="rv-col" style={{ textTransform: "uppercase", fontSize: 11, fontWeight: 600 }}>
                {query ? (
                  <HighlightedText html={null} fallback={it.manufacturer ?? "—"} query={query} maxLength={32} />
                ) : (
                  it.manufacturer ?? "—"
                )}
              </div>
            )}
            {isCol("model") && (
              <div className="rv-col" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                {query ? (
                  <HighlightedText html={null} fallback={it.model_name ?? "—"} query={query} maxLength={32} />
                ) : (
                  it.model_name ?? "—"
                )}
              </div>
            )}
            {isCol("series") && (
              <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5 }}>
                <strong>{it.n_series}</strong>·{it.n_instances}
              </div>
            )}
            {isCol("size") && (
              <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5 }}>
                {fmtBytes(it.total_bytes)}
              </div>
            )}
            {isCol("description") && (
              <div
                className="rv-col"
                data-testid="v3-row-description"
                style={{
                  fontSize: 12,
                  color: "#0f172a",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
                title={
                  it.study_description && it.study_description.length > 0
                    ? it.study_description
                    : undefined
                }
              >
                {(() => {
                  // text-search-description Phase 1.5 — 4-state cell render:
                  //   - undefined / null  → flag-off or pre-Phase-1.5 → "—"
                  //   - ""                → scrubbed but all stripped → PhiPendingBadge
                  //   - "..."             → normal text (highlight if q present)
                  if (it.study_description == null) {
                    return <span style={{ color: "var(--rv-stone-400)" }}>—</span>;
                  }
                  if (it.study_description === "") {
                    return <PhiPendingBadge variant="cell" locale={locale} />;
                  }
                  return query ? (
                    <HighlightedText
                      html={it.highlight_snippet}
                      fallback={it.study_description}
                      query={query}
                      maxLength={48}
                    />
                  ) : (
                    it.study_description
                  );
                })()}
              </div>
            )}
            {isCol("uid") && (
              <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "var(--rv-stone-500)" }}>
                {uidTail(it.pseudo_study_uid)}
              </div>
            )}
            <div className="rv-col" style={{ display: "flex", justifyContent: "flex-end" }}>
              <Link
                href={`/studies/${encodeURIComponent(it.pseudo_study_uid)}`}
                data-testid="v3-row-view"
                style={{
                  padding: "3px 8px",
                  background: "var(--rv-navy-900)",
                  color: "#fff",
                  borderRadius: 3,
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                {L(locale, "보기 →", "View →")}
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export const SORTABLE_KEYS = SORTABLE;
