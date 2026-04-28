"use client";

/**
 * <SeriesMiniCardListV4> — right-rail SERIES card with click-to-activate
 * rows + sticky head + scrollable body. Bidirectional sync with the
 * left <SeriesPicker>: when activeSeriesUid changes from the picker (or
 * keyboard shortcut), the matching row gets `--active` styling and
 * scrolls into view.
 *
 * Wraps the existing v3 SeriesMiniRow shape but adds:
 *   - role="button" + Enter/Space activation,
 *   - active stripe (`--active`) + disabled state (`--disabled`),
 *   - scrollIntoView({block:'nearest', behavior:'smooth'}) on activate,
 *   - max-height 240px with sticky head (design-spec §4.2 v0.2 #3).
 *
 * The disabled rows still appear in the list (so the user knows about
 * pending series 11 in a 12-series cardiac MR study) but click is a
 * no-op.
 */

import { useEffect, useRef } from "react";
import clsx from "clsx";
import type { Locale } from "@/lib/i18n";

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

export type SeriesMiniItemV4 = {
  pseudo_series_uid: string;
  modality: string | null;
  n_instances: number;
  description?: string | null;
  slice_thickness_mm?: number | null;
  resolution_w?: number | null;
  resolution_h?: number | null;
  /** "generated" → clickable; otherwise disabled. */
  preview_status?:
    | "generated"
    | "skipped"
    | "quarantined"
    | "pending"
    | null;
};

export type SeriesMiniCardListV4Props = {
  series: SeriesMiniItemV4[];
  activeSeriesUid: string | null;
  onSelect: (seriesUid: string) => void;
  locale?: Locale;
};

export function SeriesMiniCardListV4({
  series,
  activeSeriesUid,
  onSelect,
  locale = "en",
}: SeriesMiniCardListV4Props) {
  void locale;
  const totalInst = series.reduce((s, x) => s + (x.n_instances ?? 0), 0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRowRef = useRef<HTMLDivElement>(null);

  // Auto scrollIntoView when active changes (FR-DV-2 v0.2 #3). Guarded
  // because jsdom does not implement scrollIntoView.
  useEffect(() => {
    if (!activeRowRef.current) return;
    if (typeof window === "undefined") return;
    if (typeof activeRowRef.current.scrollIntoView !== "function") return;
    const reduce = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    activeRowRef.current.scrollIntoView({
      block: "nearest",
      behavior: reduce ? "auto" : "smooth",
    });
  }, [activeSeriesUid]);

  return (
    <div
      className="rv-detail-meta-card rv-detail-meta-card--series-v4"
      data-testid="dv-meta-card-series"
    >
      <div className="rv-detail-meta-card__head rv-detail-meta-card__head--sticky">
        <span>Series</span>
        {series.length > 0 ? (
          <span className="rv-detail-meta-card__head__count">
            {series.length} series · {totalInst} inst
          </span>
        ) : null}
      </div>
      <div className="rv-series-mini-scroll" ref={scrollRef}>
        {series.length === 0 ? (
          <div className="rv-detail-meta-row" data-testid="dv-meta-card-series-empty">
            <span className="rv-detail-meta-row__k">No series</span>
            <span className="rv-detail-meta-row__v rv-detail-meta-row__v--missing">
              —
            </span>
          </div>
        ) : (
          series.map((s, i) => {
            const isActive = s.pseudo_series_uid === activeSeriesUid;
            const isDisabled =
              s.preview_status != null && s.preview_status !== "generated";
            const title =
              s.description && s.description.trim().length > 0
                ? s.description.trim()
                : `Series ${i + 1}`;
            const subParts: string[] = [];
            if (s.modality) subParts.push(s.modality);
            if (s.slice_thickness_mm != null)
              subParts.push(`${s.slice_thickness_mm.toFixed(1)} mm`);
            if (s.resolution_w != null && s.resolution_h != null) {
              subParts.push(
                s.resolution_w === s.resolution_h
                  ? `${s.resolution_w}²`
                  : `${s.resolution_w}×${s.resolution_h}`,
              );
            }
            const sub = subParts.length > 0 ? subParts.join(" · ") : "—";
            return (
              <div
                key={s.pseudo_series_uid}
                ref={isActive ? activeRowRef : null}
                className={clsx(
                  "rv-series-mini",
                  isActive && "rv-series-mini--active",
                  isDisabled && "rv-series-mini--disabled",
                )}
                role="button"
                tabIndex={isDisabled ? -1 : 0}
                aria-pressed={isActive}
                aria-disabled={isDisabled || undefined}
                data-testid={`dv-series-mini-card-${i}`}
                title={
                  isDisabled
                    ? s.preview_status === "pending"
                      ? "Preview not yet generated"
                      : s.preview_status === "quarantined"
                        ? "Defacing failed — preview quarantined"
                        : s.preview_status === "skipped"
                          ? "Burned-in text detected — preview skipped"
                          : "Preview unavailable"
                    : undefined
                }
                onClick={() => {
                  if (isDisabled) return;
                  onSelect(s.pseudo_series_uid);
                }}
                onKeyDown={(e) => {
                  if (isDisabled) return;
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(s.pseudo_series_uid);
                  }
                }}
              >
                <div className="rv-series-mini__num">{i + 1}</div>
                <div style={{ minWidth: 0 }}>
                  <span className="rv-series-mini__title" title={title}>
                    <span
                      className={clsx(
                        "rv-series-picker__dot",
                        modalityDotClass(s.modality),
                      )}
                      aria-hidden
                      style={{ marginRight: 6 }}
                    />
                    {title}
                  </span>
                  <span className="rv-series-mini__sub">{sub}</span>
                </div>
                <div className="rv-series-mini__count">
                  {s.preview_status != null &&
                  s.preview_status !== "generated" ? (
                    <span className="rv-series-mini__pending">
                      {s.preview_status}
                    </span>
                  ) : (
                    <>
                      {s.n_instances.toLocaleString()} inst
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
