"use client";

/**
 * <KCDAutocomplete> — buyer-search-v3 FR-V3-UI-4.
 *
 * Triple-ontology autocomplete (KCD-8 / SNOMED / RadLex). Typing queries
 * /api/search/kcd-autocomplete?q=&limit=12 with a 200 ms debounce. Selecting
 * a row fires `onSelect(item)` and clears the input — the parent is
 * responsible for adding the chosen `code` to the `kcd_code` filter.
 *
 * Failure mode: a 5xx response renders a passive "ontology temporarily
 * unavailable — search by free text" hint inside the dropdown so the buyer
 * can keep typing into the chip search instead.
 */

import { useEffect, useRef, useState } from "react";

export type KCDOntology = "KCD-8" | "SNOMED" | "RadLex";

export type KCDItem = {
  ontology: KCDOntology;
  code: string;
  label_ko: string;
  label_en: string;
};

export type KCDAutocompleteProps = {
  value: string;
  onChange: (value: string) => void;
  onSelect: (item: KCDItem) => void;
  placeholder?: string;
  locale?: "ko" | "en";
  /**
   * Override the BFF endpoint (tests inject a mock). Default `/api/search/kcd-autocomplete`.
   */
  endpoint?: string;
};

export function KCDAutocomplete({
  value,
  onChange,
  onSelect,
  placeholder = "협심증 / Angina / I20 — KCD-8 · SNOMED · RadLex",
  locale = "en",
  endpoint = "/api/search/kcd-autocomplete",
}: KCDAutocompleteProps) {
  const [items, setItems] = useState<KCDItem[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // Debounced fetch.
  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    if (!value.trim()) {
      setItems([]);
      setOpen(false);
      setError(null);
      return;
    }
    debounce.current = setTimeout(async () => {
      try {
        const url = new URL(endpoint, window.location.origin);
        url.searchParams.set("q", value);
        url.searchParams.set("limit", "12");
        const res = await fetch(url.toString().replace(window.location.origin, ""));
        if (!res.ok) {
          setError("ontology temporarily unavailable · search by free text");
          setItems([]);
          setOpen(true);
          return;
        }
        const data: { items: KCDItem[] } = await res.json();
        setItems(data.items ?? []);
        setError(null);
        setOpen(true);
        setActive(0);
      } catch {
        setError("ontology temporarily unavailable · search by free text");
        setItems([]);
        setOpen(true);
      }
    }, 200);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
  }, [value, endpoint]);

  // Click outside closes.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function handleSelect(item: KCDItem) {
    onSelect(item);
    onChange("");
    setOpen(false);
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || items.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(items.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleSelect(items[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={wrapRef} style={{ position: "relative", flex: 1, maxWidth: 720 }}>
      <input
        data-testid="kcd-autocomplete-input"
        type="text"
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls="rv-kcd-listbox"
        aria-activedescendant={
          open && items.length > 0 ? `rv-kcd-row-${active}` : undefined
        }
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => {
          if (items.length > 0 || error) setOpen(true);
        }}
        onKeyDown={onKey}
        style={{
          width: "100%",
          padding: "11px 14px 11px 14px",
          fontSize: 14,
          border: "1.5px solid var(--rv-stone-300)",
          borderRadius: 6,
          background: "#fff",
          color: "var(--rv-stone-900)",
        }}
      />
      {open && (items.length > 0 || error) ? (
        <div
          id="rv-kcd-listbox"
          role="listbox"
          className="rv-autocomplete"
          data-testid="kcd-autocomplete-list"
        >
          {error ? (
            <div
              style={{
                padding: "10px 14px",
                fontSize: 12,
                color: "var(--rv-stone-500)",
                background: "var(--rv-stone-50)",
              }}
              data-testid="kcd-autocomplete-error"
            >
              {error}
            </div>
          ) : (
            items.map((it, idx) => (
              <div
                key={`${it.ontology}-${it.code}-${idx}`}
                id={`rv-kcd-row-${idx}`}
                role="option"
                aria-selected={idx === active}
                className="rv-autocomplete__row"
                onMouseDown={(e) => {
                  // mousedown so the input doesn't blur first.
                  e.preventDefault();
                  handleSelect(it);
                }}
                onMouseEnter={() => setActive(idx)}
              >
                <div className="rv-autocomplete__code">{it.code}</div>
                <div style={{ fontWeight: 600, color: "var(--rv-stone-900)" }}>
                  {locale === "ko" ? it.label_ko : it.label_ko}
                </div>
                <div style={{ color: "var(--rv-stone-600)", fontStyle: "italic" }}>
                  {it.label_en}
                </div>
                <div
                  className={`rv-autocomplete__source rv-autocomplete__source--${it.ontology
                    .toLowerCase()
                    .replace("-8", "")
                    .replace("kcd", "kcd")}`}
                >
                  {it.ontology}
                </div>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
