"use client";

/**
 * <FacetSidebarV3> — buyer-search-v3 FR-V3-UI-2.
 *
 * 5 accordion groups (Hospital · Clinical · Patient · Imaging · Time). The
 * "De-ID verified" facet is intentionally absent: anonymisation is a baseline
 * platform guarantee (every row), not a filter — surfacing it as a facet
 * would imply unverified rows exist on the site.
 */

import { useState } from "react";
import { HospitalBadge } from "./HospitalBadge";
import { ModalityDot } from "./ModalityDot";
import { AgeRangeInput } from "./AgeRangeInput";

export type FacetItem = { value: string | null; count: number };

export type V3FacetState = {
  modality: string[];
  body_part: string[];
  sex: string[];
  manufacturer: string[];
  year: string[];
  hospital_region: string[];
  kcd_code: string[];
  age_min: number;
  age_max: number;
};

export const EMPTY_V3_FACET_STATE: V3FacetState = {
  modality: [],
  body_part: [],
  sex: [],
  manufacturer: [],
  year: [],
  hospital_region: [],
  kcd_code: [],
  age_min: 0,
  age_max: 120,
};

export type FacetSidebarV3Props = {
  values: V3FacetState;
  onChange: (next: V3FacetState) => void;
  facets: {
    modality?: FacetItem[];
    body_part?: FacetItem[];
    sex?: FacetItem[];
    manufacturer?: FacetItem[];
    year?: FacetItem[];
    hospital_region?: FacetItem[];
    kcd_code?: FacetItem[];
  };
  resultCount?: number;
  locale?: "ko" | "en";
};

function L(locale: "ko" | "en", ko: string, en: string): string {
  return locale === "ko" ? ko : en;
}

export function FacetSidebarV3({
  values,
  onChange,
  facets,
  resultCount,
  locale = "en",
}: FacetSidebarV3Props) {
  const [open, setOpen] = useState({
    hospital: true,
    clinical: true,
    patient: true,
    imaging: true,
    time: false,
  });

  function toggle(group: keyof typeof open) {
    setOpen((prev) => ({ ...prev, [group]: !prev[group] }));
  }

  function toggleListItem(key: keyof V3FacetState, val: string) {
    const cur = values[key] as string[];
    const next = cur.includes(val)
      ? cur.filter((x) => x !== val)
      : [...cur, val];
    onChange({ ...values, [key]: next });
  }

  return (
    <aside className="rv-sidebar" aria-label={L(locale, "필터", "Filters")}>
      {/* Group 1 — Hospital */}
      <Accordion
        title={L(locale, "병원", "Hospital")}
        open={open.hospital}
        onToggle={() => toggle("hospital")}
        testid="facet-hospital"
      >
        {(facets.hospital_region ?? []).map((f) => {
          const v = String(f.value ?? "");
          return (
            <FacetCheckRow
              key={`hreg-${v}`}
              checked={values.hospital_region.includes(v)}
              onChange={() => toggleListItem("hospital_region", v)}
              count={f.count}
            >
              <HospitalBadge regionPseudo={v} />
            </FacetCheckRow>
          );
        })}
      </Accordion>

      {/* Group 2 — Clinical (KCD + Body part) */}
      <Accordion
        title={L(locale, "임상 정보", "Clinical")}
        open={open.clinical}
        onToggle={() => toggle("clinical")}
        testid="facet-clinical"
      >
        <SubLabel>{L(locale, "KCD 코드", "KCD code")}</SubLabel>
        {(facets.kcd_code ?? []).slice(0, 10).map((f) => {
          const v = String(f.value ?? "");
          return (
            <FacetCheckRow
              key={`kcd-${v}`}
              checked={values.kcd_code.includes(v)}
              onChange={() => toggleListItem("kcd_code", v)}
              count={f.count}
            >
              <span
                style={{
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 11.5,
                }}
              >
                {v || "—"}
              </span>
            </FacetCheckRow>
          );
        })}
        <SubLabel>{L(locale, "부위", "Body part")}</SubLabel>
        {(facets.body_part ?? []).slice(0, 10).map((f) => {
          const v = String(f.value ?? "");
          return (
            <FacetCheckRow
              key={`bp-${v}`}
              checked={values.body_part.includes(v)}
              onChange={() => toggleListItem("body_part", v)}
              count={f.count}
            >
              <span style={{ fontSize: 12.5 }}>{v}</span>
            </FacetCheckRow>
          );
        })}
      </Accordion>

      {/* Group 3 — Patient (Sex + Age range) */}
      <Accordion
        title={L(locale, "환자 정보", "Patient")}
        open={open.patient}
        onToggle={() => toggle("patient")}
        testid="facet-patient"
      >
        <SubLabel>{L(locale, "성별", "Sex")}</SubLabel>
        {(facets.sex ?? []).map((f) => {
          const v = String(f.value ?? "");
          if (!v) return null;
          return (
            <FacetCheckRow
              key={`sex-${v}`}
              checked={values.sex.includes(v)}
              onChange={() => toggleListItem("sex", v)}
              count={f.count}
            >
              <span style={{ fontSize: 12.5 }}>{v}</span>
            </FacetCheckRow>
          );
        })}
        <SubLabel>{L(locale, "나이 (세)", "Age (years)")}</SubLabel>
        <AgeRangeInput
          valueMin={values.age_min}
          valueMax={values.age_max}
          onChange={(lo, hi) =>
            onChange({ ...values, age_min: lo, age_max: hi })
          }
          countHint={
            resultCount !== undefined
              ? `${resultCount} ${L(locale, "건", "studies")}`
              : undefined
          }
          locale={locale}
        />
      </Accordion>

      {/* Group 4 — Imaging */}
      <Accordion
        title={L(locale, "영상 기술", "Imaging")}
        open={open.imaging}
        onToggle={() => toggle("imaging")}
        testid="facet-imaging"
      >
        <SubLabel>{L(locale, "모달리티", "Modality")}</SubLabel>
        {(facets.modality ?? []).map((f) => {
          const v = String(f.value ?? "");
          return (
            <FacetCheckRow
              key={`mod-${v}`}
              checked={values.modality.includes(v)}
              onChange={() => toggleListItem("modality", v)}
              count={f.count}
            >
              <ModalityDot modality={v} />
            </FacetCheckRow>
          );
        })}
      </Accordion>

      {/* Group 5 — Time */}
      <Accordion
        title={L(locale, "시간", "Time")}
        open={open.time}
        onToggle={() => toggle("time")}
        testid="facet-time"
      >
        {(facets.year ?? []).slice(0, 10).map((f) => {
          const v = String(f.value ?? "");
          return (
            <FacetCheckRow
              key={`year-${v}`}
              checked={values.year.includes(v)}
              onChange={() => toggleListItem("year", v)}
              count={f.count}
            >
              <span style={{ fontSize: 12.5 }}>{v}</span>
            </FacetCheckRow>
          );
        })}
      </Accordion>
    </aside>
  );
}

function Accordion({
  title,
  open,
  onToggle,
  children,
  testid,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  testid?: string;
}) {
  return (
    <div className="rv-acc__group" data-testid={testid}>
      <button
        type="button"
        className="rv-acc__head"
        aria-expanded={open}
        onClick={onToggle}
      >
        <span>{title}</span>
        <span aria-hidden style={{ fontSize: 10 }}>{open ? "▾" : "▸"}</span>
      </button>
      {open ? <div className="rv-acc__body">{children}</div> : null}
    </div>
  );
}

function SubLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10.5,
        color: "var(--rv-stone-500)",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        margin: "8px 0 6px",
      }}
    >
      {children}
    </div>
  );
}

function FacetCheckRow({
  checked,
  onChange,
  count,
  children,
}: {
  checked: boolean;
  onChange: () => void;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 0",
        fontSize: 13,
        cursor: "pointer",
        color: "var(--rv-stone-700)",
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <input type="checkbox" checked={checked} onChange={onChange} />
        {children}
      </span>
      {count !== undefined ? (
        <span
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: 11,
            color: "var(--rv-stone-500)",
          }}
        >
          {count}
        </span>
      ) : null}
    </label>
  );
}
