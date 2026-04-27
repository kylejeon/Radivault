"use client";

/**
 * <AutocompleteDropdown> — text-search-description FR-TS-8 / design-spec §7.
 *
 * Listbox of trigram-backed suggestions surfaced under <SearchBar> while the
 * buyer is typing. Pure presentational + keyboard navigation; the actual
 * fetch + debounce live in the parent <SearchBar> so a single owner controls
 * loading state.
 */

import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";

export type AutocompleteSuggestion = {
  text: string;
  field: string;
  score: number;
};

export type AutocompleteDropdownProps = {
  open: boolean;
  loading: boolean;
  query: string;
  suggestions: AutocompleteSuggestion[];
  focusedIndex: number;
  locale: Locale;
  onPick: (s: AutocompleteSuggestion) => void;
  onHover: (index: number) => void;
  /** Caller-supplied id used for aria-controls plumbing on the input. */
  listboxId: string;
};

const FIELD_BADGE_BG: Record<string, { bg: string; fg: string }> = {
  body_part: { bg: "#f8fafc", fg: "#64748b" },
  modality: { bg: "#f8fafc", fg: "#64748b" },
  kcd_label_en: { bg: "#ccfbf1", fg: "#0f766e" },
  kcd_label_ko: { bg: "#ccfbf1", fg: "#0f766e" },
  manufacturer: { bg: "#f8fafc", fg: "#64748b" },
  model_name: { bg: "#f8fafc", fg: "#64748b" },
  // text-search-description Phase 1.5 (design-spec §11.1) — STUDY DESC uses
  // the lighter teal-50 to differentiate from KCD's teal-100; PROTOCOL is
  // neutral (slate, same family as body_part).
  study_description: { bg: "#f0fdfa", fg: "#0f766e" },
  protocol_name: { bg: "#f8fafc", fg: "#64748b" },
};

function fieldLabel(field: string, locale: "en" | "ko"): string {
  // Compact label rendered inside the right-side badge. UPPERCASE for new
  // Phase 1.5 badges per Kyle decision; legacy badges keep lowercase.
  if (field === "study_description") {
    return locale === "ko" ? "검사 설명" : "STUDY DESC";
  }
  if (field === "protocol_name") {
    return locale === "ko" ? "프로토콜" : "PROTOCOL";
  }
  switch (field) {
    case "body_part":
      return "body part";
    case "kcd_label_en":
      return "KCD";
    case "kcd_label_ko":
      return "KCD";
    case "model_name":
      return "model";
    default:
      return field;
  }
}

/**
 * Render the matched substring underlined + teal so the buyer can see why a
 * given suggestion surfaced. Case-insensitive — but preserves the suggestion's
 * original casing in the rendered output.
 */
function renderMatch(text: string, query: string): JSX.Element {
  const q = query.trim();
  if (!q) return <>{text}</>;
  const lower = text.toLowerCase();
  const ql = q.toLowerCase();
  const idx = lower.indexOf(ql);
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <span
        style={{
          fontWeight: 600,
          color: "#0f766e",
          textDecoration: "underline",
          textUnderlineOffset: 2,
        }}
      >
        {text.slice(idx, idx + ql.length)}
      </span>
      {text.slice(idx + ql.length)}
    </>
  );
}

export function AutocompleteDropdown({
  open,
  loading,
  query,
  suggestions,
  focusedIndex,
  locale,
  onPick,
  onHover,
  listboxId,
}: AutocompleteDropdownProps): JSX.Element | null {
  if (!open) return null;
  const t = getDict(locale).search.searchBar;
  const showLoadingRow = loading && suggestions.length === 0;
  const showEmpty = !loading && suggestions.length === 0 && query.trim().length >= 1;

  return (
    <ul
      id={listboxId}
      role="listbox"
      aria-label={t.ariaLabel}
      data-testid="ts-autocomplete-listbox"
      style={{
        position: "absolute",
        top: "calc(100% + 4px)",
        left: 0,
        right: 0,
        margin: 0,
        padding: 0,
        listStyle: "none",
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        borderRadius: 8,
        boxShadow:
          "0 10px 25px rgba(15, 23, 42, 0.10), 0 4px 10px rgba(15, 23, 42, 0.08)",
        zIndex: 50,
        maxHeight: 400,
        overflowY: "auto",
      }}
    >
      {showLoadingRow ? (
        <li
          role="option"
          aria-selected={false}
          style={{
            padding: "10px 16px",
            fontSize: 13,
            color: "#64748b",
            fontStyle: "italic",
          }}
        >
          {t.loadingSuggestions}
        </li>
      ) : null}
      {showEmpty ? (
        <li
          role="option"
          aria-selected={false}
          style={{
            padding: "10px 16px",
            fontSize: 13,
            color: "#64748b",
          }}
        >
          {t.noSuggestions}
        </li>
      ) : null}
      {suggestions.map((s, idx) => {
        const isFocused = idx === focusedIndex;
        const badge = FIELD_BADGE_BG[s.field] ?? { bg: "#f8fafc", fg: "#64748b" };
        return (
          <li
            key={`${s.field}::${s.text}`}
            id={`ts-suggestion-${idx}`}
            role="option"
            aria-selected={isFocused}
            data-testid="ts-suggestion"
            data-field={s.field}
            onMouseDown={(e) => {
              // mousedown beats blur; use it so the click registers before
              // the input loses focus and closes the dropdown.
              e.preventDefault();
              onPick(s);
            }}
            onMouseEnter={() => onHover(idx)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "10px 16px",
              cursor: "pointer",
              background: isFocused ? "#eff6ff" : "transparent",
              borderLeft: isFocused
                ? "3px solid #2563eb"
                : "3px solid transparent",
              fontSize: 13,
              color: "#0f172a",
            }}
          >
            <span style={{ flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {renderMatch(s.text, query)}
            </span>
            <span
              style={{
                flex: "0 0 auto",
                fontSize: 11,
                fontWeight: 500,
                padding: "2px 8px",
                background: badge.bg,
                color: badge.fg,
                borderRadius: 999,
                // Phase 1.5: STUDY DESC / PROTOCOL keep UPPERCASE (Kyle).
                // Legacy lowercase still applied to body_part / modality.
                textTransform:
                  s.field === "study_description" || s.field === "protocol_name"
                    ? "none"
                    : "lowercase",
              }}
              aria-label={`Match field: ${s.field}`}
            >
              {fieldLabel(s.field, locale === "ko" ? "ko" : "en")}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
