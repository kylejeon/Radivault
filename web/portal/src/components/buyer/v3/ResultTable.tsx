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

import Link from "next/link";
import { HospitalBadge } from "./HospitalBadge";
import { ModalityDot } from "./ModalityDot";

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

export function ResultTable({
  items,
  sortKey,
  sortDir,
  onSort,
  selected,
  onToggleRow,
  locale = "en",
}: ResultTableProps) {
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
      <div className="rv-result-table__row rv-result-table__row--head" role="row">
        <div className="rv-col-stripe" />
        <div className="rv-col rv-col-check" />
        {header("hospital", "병원", "Hospital")}
        {header("examdate", "촬영일", "Exam Date")}
        {header("modality", "모달리티", "Modality")}
        {header("bodypart", "부위", "BodyPart")}
        {header("kcd", "KCD", "KCD")}
        {staticHead("성별", "Sex")}
        {header("age", "나이", "Age")}
        {header("mfg", "제조사", "Manufacturer")}
        {header("model", "모델", "Model")}
        {staticHead("Sr·Inst", "Sr · Inst")}
        {header("size", "용량", "Size")}
        {staticHead("UID", "UID")}
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
            <div className="rv-col">
              <HospitalBadge regionPseudo={region} />
            </div>
            <div className="rv-col rv-col-mono">
              {it.study_date_shifted ?? "—"}
            </div>
            <div className="rv-col" style={{ display: "flex", alignItems: "center" }}>
              <ModalityDot modality={it.modality} />
            </div>
            <div className="rv-col" style={{ textTransform: "uppercase", fontWeight: 500, fontSize: 12 }}>
              {it.body_part ?? "—"}
            </div>
            <div className="rv-col rv-col-kcd">
              {it.kcd_code ? (
                <>
                  <span className="rv-kcd-chip">{it.kcd_code}</span>
                  <span className="rv-kcd-label">
                    {locale === "ko" ? it.kcd_label_ko ?? "" : it.kcd_label_en ?? ""}
                  </span>
                </>
              ) : (
                <span style={{ color: "var(--rv-stone-400)" }}>—</span>
              )}
            </div>
            <div className="rv-col" style={{ textAlign: "center", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5, fontWeight: 700, color: "var(--rv-navy-900)" }}>
              {it.sex ?? "—"}
            </div>
            <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5, fontWeight: 600 }}>
              {it.patient_age ?? "—"}
            </div>
            <div className="rv-col" style={{ textTransform: "uppercase", fontSize: 11, fontWeight: 600 }}>
              {it.manufacturer ?? "—"}
            </div>
            <div className="rv-col" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
              {it.model_name ?? "—"}
            </div>
            <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5 }}>
              <strong>{it.n_series}</strong>·{it.n_instances}
            </div>
            <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11.5 }}>
              {fmtBytes(it.total_bytes)}
            </div>
            <div className="rv-col" style={{ textAlign: "right", fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "var(--rv-stone-500)" }}>
              {uidTail(it.pseudo_study_uid)}
            </div>
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
