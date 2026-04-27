"use client";

/**
 * <SearchBar> — text-search-description FR-TS-1 / design-spec §6.
 *
 * Hero-area free-text input that owns:
 *   - the local `q` state (mirrored to the parent via onChange)
 *   - a 200 ms debounced fetch against /api/search/autocomplete
 *   - keyboard navigation across the dropdown listbox
 *   - the masked-query badge (driven by ``flaggedPatterns`` from the parent)
 *
 * The parent <SearchAppV3> handles URL ``?q=`` sync, the actual search
 * fetch, and result rendering. Keeping <SearchBar> presentational means
 * the component is reusable from any future host (hospital console, etc).
 */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  AutocompleteDropdown,
  type AutocompleteSuggestion,
} from "./AutocompleteDropdown";
import { MaskedQueryBadge } from "./MaskedQueryBadge";
import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";

export type SearchBarProps = {
  value: string;
  onChange: (q: string) => void;
  /** Triggered on Enter or autocomplete pick — parent should fetch results. */
  onSubmit: (q: string) => void;
  locale: Locale;
  /** Patterns surfaced by the latest search response (FR-TS-10). */
  flaggedPatterns?: string[];
  /** When true the bar renders the explicit Search button (mobile). */
  forceSubmitButton?: boolean;
  /** Test hook — disable autocomplete fetch (used by storybook/unit tests). */
  disableAutocomplete?: boolean;
  className?: string;
};

const DEBOUNCE_MS = 200;
const MIN_CHARS = 2;
const FETCH_LIMIT = 10;

type AutocompleteResponse = {
  suggestions: AutocompleteSuggestion[];
  computed_at?: string;
  error?: string;
};

export function SearchBar({
  value,
  onChange,
  onSubmit,
  locale,
  flaggedPatterns,
  forceSubmitButton = false,
  disableAutocomplete = false,
  className,
}: SearchBarProps): JSX.Element {
  const t = getDict(locale).search.searchBar;
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fetchTokenRef = useRef(0);
  const listboxId = useId();

  const [focused, setFocused] = useState(false);
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const dropdownOpen = useMemo(() => {
    if (!focused) return false;
    if (value.trim().length < MIN_CHARS) return false;
    return true;
  }, [focused, value]);

  // Debounced autocomplete fetch.
  useEffect(() => {
    if (disableAutocomplete) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim().length < MIN_CHARS) {
      setSuggestions([]);
      setLoading(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      const token = ++fetchTokenRef.current;
      setLoading(true);
      const url = `/api/search/autocomplete?q=${encodeURIComponent(
        value.trim(),
      )}&limit=${FETCH_LIMIT}`;
      fetch(url, { credentials: "same-origin" })
        .then(async (r) => {
          if (!r.ok) {
            // FR-TS-AVAIL-2 — silent dropdown close on autocomplete failure.
            // Search itself still works.
            if (token === fetchTokenRef.current) {
              setSuggestions([]);
              setLoading(false);
            }
            return;
          }
          const body = (await r.json()) as AutocompleteResponse;
          if (token !== fetchTokenRef.current) return;
          setSuggestions(body.suggestions ?? []);
          setLoading(false);
          setFocusedIndex(-1);
        })
        .catch(() => {
          if (token !== fetchTokenRef.current) return;
          setSuggestions([]);
          setLoading(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [value, disableAutocomplete]);

  // Click-outside to close the dropdown.
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!wrapperRef.current) return;
      if (!wrapperRef.current.contains(e.target as Node)) {
        setFocused(false);
        setFocusedIndex(-1);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < suggestions.length) {
        const picked = suggestions[focusedIndex];
        onChange(picked.text);
        onSubmit(picked.text);
      } else {
        onSubmit(value);
      }
      setFocused(false);
      setFocusedIndex(-1);
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      if (suggestions.length > 0 || loading) {
        setSuggestions([]);
        setFocusedIndex(-1);
        // Keep focus + value; second Esc clears.
      } else if (value.length > 0) {
        onChange("");
      }
      return;
    }
    if (e.key === "ArrowDown") {
      if (suggestions.length === 0) return;
      e.preventDefault();
      setFocusedIndex((idx) => (idx + 1) % suggestions.length);
      return;
    }
    if (e.key === "ArrowUp") {
      if (suggestions.length === 0) return;
      e.preventDefault();
      setFocusedIndex((idx) =>
        idx <= 0 ? suggestions.length - 1 : idx - 1,
      );
      return;
    }
    if (e.key === "Home") {
      if (suggestions.length === 0) return;
      e.preventDefault();
      setFocusedIndex(0);
    }
    if (e.key === "End") {
      if (suggestions.length === 0) return;
      e.preventDefault();
      setFocusedIndex(suggestions.length - 1);
    }
  }

  function handleClear() {
    onChange("");
    setSuggestions([]);
    setFocusedIndex(-1);
    inputRef.current?.focus();
  }

  function handlePick(s: AutocompleteSuggestion) {
    onChange(s.text);
    onSubmit(s.text);
    setSuggestions([]);
    setFocusedIndex(-1);
    setFocused(false);
  }

  const showSubmit = forceSubmitButton;

  return (
    <div
      ref={wrapperRef}
      role="search"
      data-testid="ts-search-bar"
      className={className}
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        height: 56,
        background: "#ffffff",
        border: focused
          ? "2px solid #0d9488"
          : "1px solid #e2e8f0",
        borderRadius: 8,
        boxShadow: focused
          ? "0 0 0 3px rgba(13, 148, 136, 0.15)"
          : "0 1px 2px rgba(15, 23, 42, 0.04)",
        transition: "border-color 0.15s ease, box-shadow 0.15s ease",
      }}
    >
      <span
        aria-hidden
        style={{
          flex: "0 0 auto",
          padding: "0 10px 0 16px",
          fontSize: 16,
          color: focused ? "#0d9488" : "#64748b",
          display: "flex",
          alignItems: "center",
        }}
      >
        {/* Inline magnifier so we don't pull lucide for one icon. */}
        🔍
      </span>
      {/* design-spec §6.6 calls for role="searchbox" + aria-expanded so the
          input announces both its semantic role and the dropdown state. The
          jsx-a11y plugin is overly conservative here (WAI-ARIA 1.2 allows
          aria-expanded on searchbox with the combobox pattern); suppress. */}
      {/* eslint-disable-next-line jsx-a11y/role-supports-aria-props */}
      <input
        ref={inputRef}
        type="search"
        role="searchbox"
        aria-label={t.ariaLabel}
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-expanded={dropdownOpen}
        aria-activedescendant={
          focusedIndex >= 0 ? `ts-suggestion-${focusedIndex}` : undefined
        }
        data-testid="ts-search-input"
        placeholder={t.placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onKeyDown={handleKeyDown}
        // Browsers default to "off" for type=search but be explicit.
        autoComplete="off"
        spellCheck={false}
        style={{
          flex: 1,
          minWidth: 0,
          height: "100%",
          padding: "0 12px",
          border: "none",
          outline: "none",
          background: "transparent",
          fontSize: 16,
          color: "#0f172a",
          fontFamily:
            "Pretendard, Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        }}
      />
      {flaggedPatterns && flaggedPatterns.length > 0 ? (
        <span style={{ flex: "0 0 auto", marginRight: 8 }}>
          <MaskedQueryBadge flagged={flaggedPatterns} locale={locale} />
        </span>
      ) : null}
      {value.length > 0 ? (
        <button
          type="button"
          aria-label={t.clearAria}
          data-testid="ts-search-clear"
          onClick={handleClear}
          style={{
            flex: "0 0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 28,
            height: 28,
            marginRight: 8,
            border: "none",
            background: "transparent",
            color: "#64748b",
            cursor: "pointer",
            fontSize: 16,
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      ) : null}
      {showSubmit ? (
        <button
          type="button"
          data-testid="ts-search-submit"
          onClick={() => onSubmit(value)}
          style={{
            flex: "0 0 auto",
            height: 40,
            margin: "0 8px",
            padding: "0 14px",
            border: "none",
            borderRadius: 6,
            background: "#2563eb",
            color: "#ffffff",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {t.submitButton}
        </button>
      ) : null}
      <AutocompleteDropdown
        open={dropdownOpen}
        loading={loading}
        query={value}
        suggestions={suggestions}
        focusedIndex={focusedIndex}
        locale={locale}
        listboxId={listboxId}
        onPick={handlePick}
        onHover={(idx) => setFocusedIndex(idx)}
      />
    </div>
  );
}
