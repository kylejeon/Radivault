"use client";

/**
 * <SeriesPicker> — C-DV-SeriesPicker (design-spec-dicom-viewer §4.2,
 * v0.2 chip-row → custom dropdown).
 *
 * Custom dropdown over native <select> (rationale §4.2):
 *   - dark theme parity with the right-rail SERIES card stripe (teal-500),
 *   - per-row metadata `CT · 155 inst · 1.0 mm · 512²` rendered in mono,
 *   - disabled-with-tooltip ("Preview not yet generated") for series with
 *     `preview_status !== "generated"`,
 *   - 1-9 keyboard chip on each row that has an associated shortcut.
 *
 * Trigger (closed): `Series N of M` head + modality dot + active title.
 * Panel (open): list of all series, max-height 320px, internal scroll.
 *
 * Keyboard 1~9 hotkey is implemented at <ViewerPaneV4> level (global
 * keydown), not here — the dropdown only listens to local Enter/Space on
 * focused list items. The picker still needs to render the chip on rows
 * 1~9 so users learn the shortcut.
 */

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { ManifestSeries } from "@/components/preview/FrameSliderViewer";

const MODALITY_DOT_CLASS: Record<string, string> = {
  CT: "rv-series-picker__dot--ct",
  MR: "rv-series-picker__dot--mr",
  MG: "rv-series-picker__dot--mg",
  CR: "rv-series-picker__dot--cr",
  US: "rv-series-picker__dot--us",
  PT: "rv-series-picker__dot--pt",
};

function modalityDotClass(modality: string | null | undefined): string {
  if (!modality) return "rv-series-picker__dot--default";
  return (
    MODALITY_DOT_CLASS[modality.toUpperCase()] ??
    "rv-series-picker__dot--default"
  );
}

function formatSub(s: ManifestSeries): string {
  const parts: string[] = [];
  if (s.modality) parts.push(s.modality);
  parts.push(`${s.frame_count} inst`);
  return parts.join(" · ");
}

function seriesTitle(s: ManifestSeries, idx: number): string {
  if (s.body_part && s.body_part.trim().length > 0) return s.body_part;
  return `Series ${idx + 1}`;
}

function disabledReason(s: ManifestSeries): string {
  switch (s.preview_status) {
    case "pending":
      return "Preview not yet generated";
    case "quarantined":
      return "Defacing failed — preview quarantined";
    case "skipped":
      return "Burned-in text detected — preview skipped";
    default:
      return "Preview unavailable";
  }
}

function pendingChipLabel(s: ManifestSeries): string | null {
  if (s.preview_status === "generated") return null;
  if (s.preview_status === "quarantined") return "quarantined";
  if (s.preview_status === "skipped") return "skipped";
  return "pending";
}

export type SeriesPickerProps = {
  series: ManifestSeries[];
  activeSeriesUid: string | null;
  onSelect: (seriesUid: string) => void;
};

export function SeriesPicker({
  series,
  activeSeriesUid,
  onSelect,
}: SeriesPickerProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const activeIdx = series.findIndex(
    (s) => s.pseudo_series_uid === activeSeriesUid,
  );
  const active = activeIdx >= 0 ? series[activeIdx] : null;
  const total = series.length;

  // Outside-click close.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (wrapRef.current.contains(e.target as Node)) return;
      setOpen(false);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [open]);

  // Esc closes.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  function pick(s: ManifestSeries) {
    if (s.preview_status !== "generated") return;
    onSelect(s.pseudo_series_uid);
    setOpen(false);
  }

  return (
    <div
      className={clsx("rv-series-picker", open && "is-open")}
      ref={wrapRef}
      data-testid="dv-series-picker"
    >
      <button
        type="button"
        className="rv-series-picker__trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="dv-series-picker-list"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        data-testid="dv-series-picker-trigger"
        data-tip="Series picker (1-9 keys to switch)"
      >
        <span className="rv-series-picker__trigger__head">
          <span className="rv-series-picker__trigger__count">
            Series{" "}
            <strong data-testid="dv-series-picker-current">
              {activeIdx >= 0 ? activeIdx + 1 : "—"}
            </strong>{" "}
            <span className="rv-muted-on-dark">of</span>{" "}
            <strong data-testid="dv-series-picker-total">{total}</strong>
          </span>
          <span className="rv-series-picker__trigger__active">
            <span
              className={clsx(
                "rv-series-picker__dot",
                modalityDotClass(active?.modality),
              )}
              aria-hidden
            />
            <span className="rv-series-picker__trigger__title">
              {active ? seriesTitle(active, activeIdx) : "No series selected"}
            </span>
            {active ? (
              <span className="rv-series-picker__trigger__sub">
                {formatSub(active)}
              </span>
            ) : null}
          </span>
        </span>
        <span className="rv-series-picker__caret" aria-hidden>
          ▾
        </span>
      </button>
      <ul
        className="rv-series-picker__list"
        id="dv-series-picker-list"
        role="listbox"
        aria-label="Available series"
      >
        {series.map((s, idx) => {
          const isActive = s.pseudo_series_uid === activeSeriesUid;
          const isDisabled = s.preview_status !== "generated";
          const shortcut = idx < 9 ? String(idx + 1) : null;
          const pending = pendingChipLabel(s);
          return (
            <li
              key={s.pseudo_series_uid}
              role="option"
              tabIndex={isDisabled ? -1 : 0}
              aria-selected={isActive}
              aria-disabled={isDisabled || undefined}
              className={clsx(
                "rv-series-picker__item",
                isActive && "rv-series-picker__item--active",
                isDisabled && "rv-series-picker__item--disabled",
              )}
              data-series={idx + 1}
              data-testid={`dv-series-picker-item-${idx + 1}`}
              data-disabled={isDisabled || undefined}
              data-tip={isDisabled ? disabledReason(s) : undefined}
              onClick={(e) => {
                e.stopPropagation();
                pick(s);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  pick(s);
                }
              }}
            >
              <span className="rv-series-picker__num">{idx + 1}</span>
              <span
                className={clsx(
                  "rv-series-picker__dot",
                  modalityDotClass(s.modality),
                )}
                aria-hidden
              />
              <span className="rv-series-picker__body">
                <span className="rv-series-picker__title">
                  {seriesTitle(s, idx)}
                </span>
                <span className="rv-series-picker__sub">{formatSub(s)}</span>
              </span>
              {pending ? (
                <span className="rv-series-picker__pending">{pending}</span>
              ) : null}
              {!pending && isActive ? (
                <span className="rv-series-picker__check" aria-hidden>
                  ✓
                </span>
              ) : null}
              {!pending && !isActive && shortcut ? (
                <span className="rv-series-picker__key" aria-hidden>
                  {shortcut}
                </span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
