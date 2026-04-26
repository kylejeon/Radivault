"use client";

/**
 * <ColumnToggle> — buyer-search-v3 FR-V3-UI-1b (QA HIGH-2 / BL-1).
 *
 * Dropdown control that lets the buyer hide / show individual columns of the
 * dense ResultTable. Mirrors the v3 mockup `search.html` (`#colToggle`):
 *
 *   ┌─────────────────┐
 *   │ Show columns ▾  │
 *   └─────────────────┘
 *           │
 *           ▼ (menu, opens flush-right)
 *   ┌──────────────────────────────────┐
 *   │ Visible columns (12/12)          │
 *   ├──────────────────────────────────┤
 *   │ ☑ Hospital              always   │  ← disabled (always-on)
 *   │ ☑ Exam Date                      │
 *   │ ☑ Modality                       │
 *   │ …                                │
 *   │ ☐ Slice thickness       v0.1.5  │  ← deferred, always disabled
 *   └──────────────────────────────────┘
 *
 * The component is fully controlled — `visibleKeys` + `onChange` come from
 * the parent (SearchAppV3) so the table re-renders without re-fetching.
 *
 * Click-outside / Escape closes the menu (dispatched via document listeners
 * on mount). Locale label is supplied via `locale` prop; the menu strings
 * use the same `L(locale, ko, en)` helper pattern as the rest of v3.
 */

import { useEffect, useRef, useState } from "react";

export type ColumnDef = {
  key: string;
  labelKo: string;
  labelEn: string;
  /** "always" → checkbox forced checked + disabled; "v0.1.5"/"v0.2" → forced unchecked + disabled. */
  hint?: "always" | "v0.1.5" | "v0.2";
  /** Optional muted modality scope, e.g. "(CT)" / "(MR)". Rendered after the label in `--rv-stone-400`. */
  scope?: string;
};

export type ColumnToggleProps = {
  columns: ColumnDef[];
  visibleKeys: string[];
  onChange: (next: string[]) => void;
  locale?: "ko" | "en";
};

function L(locale: "ko" | "en", ko: string, en: string): string {
  return locale === "ko" ? ko : en;
}

/**
 * Mockup-defined column inventory (v3.2 — search.html L.371-388).
 * `Hospital` is always-on, three v0.1.5 facets (slice thickness / KVP /
 * field strength) are deferred and shown disabled with a "v0.1.5" hint.
 * 12 toggleable + Hospital(always) + 3 deferred = 16 listed (mockup label
 * "Visible columns (12/12)" excludes Hospital + the 3 deferred).
 */
export const V3_COLUMN_DEFS: ColumnDef[] = [
  { key: "hospital", labelKo: "병원", labelEn: "Hospital", hint: "always" },
  { key: "examdate", labelKo: "촬영일", labelEn: "Exam Date" },
  { key: "modality", labelKo: "모달리티", labelEn: "Modality" },
  { key: "bodypart", labelKo: "부위", labelEn: "BodyPart" },
  { key: "kcd", labelKo: "KCD", labelEn: "KCD" },
  { key: "sex", labelKo: "성별", labelEn: "Sex" },
  { key: "age", labelKo: "나이", labelEn: "Age" },
  { key: "mfg", labelKo: "제조사", labelEn: "Manufacturer" },
  { key: "model", labelKo: "모델", labelEn: "Model" },
  { key: "series", labelKo: "시리즈·인스턴스", labelEn: "Sr · Inst" },
  { key: "size", labelKo: "용량", labelEn: "Size" },
  { key: "uid", labelKo: "UID", labelEn: "UID" },
  {
    key: "slice_thickness",
    labelKo: "슬라이스 두께",
    labelEn: "Slice thickness",
    hint: "v0.1.5",
  },
  { key: "kvp", labelKo: "KVP", labelEn: "KVP", hint: "v0.1.5", scope: "(CT)" },
  {
    key: "field_strength",
    labelKo: "자기장",
    labelEn: "Field strength",
    hint: "v0.1.5",
    scope: "(MR)",
  },
];

/** Default visible set = every "always" + every untagged toggleable column. */
export const V3_DEFAULT_VISIBLE: string[] = V3_COLUMN_DEFS
  .filter((c) => c.hint !== "v0.1.5" && c.hint !== "v0.2")
  .map((c) => c.key);

export function ColumnToggle({
  columns,
  visibleKeys,
  onChange,
  locale = "en",
}: ColumnToggleProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const togglable = columns.filter(
    (c) => c.hint !== "always" && c.hint !== "v0.1.5" && c.hint !== "v0.2",
  );
  const alwaysOn = columns.filter((c) => c.hint === "always");
  const visibleTogglableCount = togglable.filter((c) =>
    visibleKeys.includes(c.key),
  ).length;
  const totalToggable = togglable.length;

  function toggle(col: ColumnDef) {
    if (col.hint === "always" || col.hint === "v0.1.5" || col.hint === "v0.2") {
      return;
    }
    const set = new Set(visibleKeys);
    if (set.has(col.key)) set.delete(col.key);
    else set.add(col.key);
    // Always preserve always-on columns in the visible set so the parent does
    // not have to special-case them downstream.
    for (const a of alwaysOn) set.add(a.key);
    onChange(Array.from(set));
  }

  return (
    <div
      ref={wrapRef}
      className={`rv-col-toggle${open ? " is-open" : ""}`}
      data-testid="v3-column-toggle"
      style={{ position: "relative" }}
    >
      <button
        type="button"
        className="rv-col-toggle__btn"
        data-testid="v3-column-toggle-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          background: "#fff",
          color: "var(--rv-stone-700)",
          border: "1px solid var(--rv-stone-300)",
          borderRadius: 4,
          fontSize: 12,
          fontWeight: 500,
          cursor: "pointer",
        }}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden
        >
          <path
            d="M2 3h8M4 6h6M6 9h4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
        <span>{L(locale, "컬럼 표시", "Show columns")}</span>
        <span aria-hidden style={{ fontSize: 10, opacity: 0.6 }}>
          ▾
        </span>
      </button>

      {open ? (
        <div
          className="rv-col-toggle__menu"
          role="menu"
          data-testid="v3-column-toggle-menu"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 6px)",
            background: "#fff",
            border: "1px solid var(--rv-stone-200)",
            borderRadius: 6,
            boxShadow: "0 8px 24px rgba(15, 23, 42, 0.12)",
            width: 260,
            padding: 8,
            zIndex: 80,
          }}
        >
          <div
            className="rv-col-toggle__menu__title"
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--rv-stone-500)",
              padding: "6px 8px 8px",
              borderBottom: "1px solid var(--rv-stone-100)",
              marginBottom: 4,
            }}
          >
            {L(
              locale,
              `표시 컬럼 (${visibleTogglableCount}/${totalToggable})`,
              `Visible columns (${visibleTogglableCount}/${totalToggable})`,
            )}
          </div>
          {columns.map((col) => {
            const deferred = col.hint === "v0.1.5" || col.hint === "v0.2";
            const always = col.hint === "always";
            const checked = always
              ? true
              : deferred
                ? false
                : visibleKeys.includes(col.key);
            return (
              <label
                key={col.key}
                className="rv-col-toggle__row"
                data-testid={`v3-column-toggle-row-${col.key}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "6px 8px",
                  fontSize: 12.5,
                  color: deferred
                    ? "var(--rv-stone-400)"
                    : "var(--rv-stone-700)",
                  borderRadius: 3,
                  cursor: deferred || always ? "not-allowed" : "pointer",
                }}
              >
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={deferred || always}
                    onChange={() => toggle(col)}
                    aria-label={`${L(locale, col.labelKo, col.labelEn)}${
                      always ? " (always shown)" : ""
                    }${deferred ? " (deferred)" : ""}`}
                    style={{ margin: 0, accentColor: "var(--rv-navy-900)" }}
                  />
                  <span>{L(locale, col.labelKo, col.labelEn)}</span>
                  {col.scope ? (
                    <span style={{ color: "var(--rv-stone-400)", fontSize: 11 }}>
                      {col.scope}
                    </span>
                  ) : null}
                </span>
                {col.hint ? (
                  <span
                    className="rv-col-toggle__row__hint"
                    style={{ fontSize: 10, color: "var(--rv-stone-500)" }}
                  >
                    {col.hint === "always"
                      ? L(locale, "항상", "always")
                      : col.hint}
                  </span>
                ) : null}
              </label>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
