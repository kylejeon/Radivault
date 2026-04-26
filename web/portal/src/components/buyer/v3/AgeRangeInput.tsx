"use client";

/**
 * <AgeRangeInput> — buyer-search-v3 FR-V3-UI-3.
 *
 * Min / Max number inputs + dual-thumb slider. Two-way sync between fields and
 * thumbs. `onChange(min, max)` fires immediately; the parent is responsible
 * for debouncing the resulting search request (see SearchAppV3, 250 ms).
 *
 * Swap correction (min > max) happens on input blur — server returns 422 for
 * the same condition (FR-V3-API-1) so the client gate prevents an obvious
 * round-trip failure.
 */

import { useEffect, useRef, useState } from "react";

export type AgeRangeInputProps = {
  min?: number;
  max?: number;
  valueMin: number;
  valueMax: number;
  onChange: (min: number, max: number) => void;
  countHint?: string;
  locale?: "ko" | "en";
};

export function AgeRangeInput({
  min = 0,
  max = 120,
  valueMin,
  valueMax,
  onChange,
  countHint,
  locale = "en",
}: AgeRangeInputProps) {
  // Local mirror so typing doesn't lose intermediate state.
  const [localMin, setLocalMin] = useState(String(valueMin));
  const [localMax, setLocalMax] = useState(String(valueMax));
  const fillRef = useRef<HTMLDivElement | null>(null);

  // Re-sync local when parent value changes.
  useEffect(() => setLocalMin(String(valueMin)), [valueMin]);
  useEffect(() => setLocalMax(String(valueMax)), [valueMax]);

  // Update fill bar between the two thumbs.
  useEffect(() => {
    if (!fillRef.current) return;
    const range = max - min || 1;
    const lo = ((valueMin - min) / range) * 100;
    const hi = 100 - ((valueMax - min) / range) * 100;
    fillRef.current.style.left = `${Math.max(0, Math.min(100, lo))}%`;
    fillRef.current.style.right = `${Math.max(0, Math.min(100, hi))}%`;
  }, [valueMin, valueMax, min, max]);

  function clamp(v: number): number {
    if (Number.isNaN(v)) return min;
    return Math.max(min, Math.min(max, v));
  }

  function commit(nextMin: number, nextMax: number) {
    let lo = clamp(nextMin);
    let hi = clamp(nextMax);
    if (lo > hi) [lo, hi] = [hi, lo]; // swap correction.
    onChange(lo, hi);
  }

  return (
    <div data-testid="age-range" style={{ padding: "4px 0 8px" }}>
      <div className="rv-age-range__inputs">
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <label
            htmlFor="rv-age-min"
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "var(--rv-stone-500)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {locale === "ko" ? "최소" : "Min"}
          </label>
          <input
            id="rv-age-min"
            data-testid="age-min-input"
            type="number"
            className="rv-age-range__input"
            min={min}
            max={max}
            step={1}
            value={localMin}
            onChange={(e) => setLocalMin(e.target.value)}
            onBlur={() => commit(Number(localMin), Number(localMax))}
            aria-label="Minimum age in years"
          />
        </div>
        <span
          aria-hidden
          style={{
            alignSelf: "center",
            color: "var(--rv-stone-400)",
            fontSize: 11,
            paddingBottom: 6,
          }}
        >
          –
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <label
            htmlFor="rv-age-max"
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "var(--rv-stone-500)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {locale === "ko" ? "최대" : "Max"}
          </label>
          <input
            id="rv-age-max"
            data-testid="age-max-input"
            type="number"
            className="rv-age-range__input"
            min={min}
            max={max}
            step={1}
            value={localMax}
            onChange={(e) => setLocalMax(e.target.value)}
            onBlur={() => commit(Number(localMin), Number(localMax))}
            aria-label="Maximum age in years"
          />
        </div>
      </div>
      <div className="rv-age-range__slider">
        <div className="rv-age-range__slider__track" />
        <div ref={fillRef} className="rv-age-range__slider__fill" />
        <input
          data-testid="age-min-slider"
          type="range"
          min={min}
          max={max}
          step={1}
          value={valueMin}
          onChange={(e) => commit(Number(e.target.value), valueMax)}
          aria-label="Minimum age slider"
        />
        <input
          data-testid="age-max-slider"
          type="range"
          min={min}
          max={max}
          step={1}
          value={valueMax}
          onChange={(e) => commit(valueMin, Number(e.target.value))}
          aria-label="Maximum age slider"
        />
      </div>
      <div
        style={{
          marginTop: 8,
          fontFamily: "JetBrains Mono, ui-monospace, monospace",
          fontSize: 10.5,
          color: "var(--rv-stone-500)",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>
          {locale === "ko"
            ? `범위: ${min}–${max}`
            : `Range: ${min}–${max}`}
        </span>
        {countHint ? (
          <span
            data-testid="age-range-count"
            style={{ color: "var(--rv-stone-700)", fontWeight: 600 }}
          >
            {countHint}
          </span>
        ) : null}
      </div>
    </div>
  );
}
