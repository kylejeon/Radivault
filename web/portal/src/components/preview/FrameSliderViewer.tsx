/**
 * FrameSliderViewer — design-spec-jpg-preview-defacing §6.
 *
 * Mounts inside the StudyDetailPanel viewer slot when the new
 * preview-manifest endpoint returns 200. For manifest-404 (legacy
 * studies) callers fall back to the existing ``SliceViewerOrFallback``
 * — silent coexistence per FR-NEWONLY-3 + §11.1.
 *
 * Layout (desktop ≥1024 px):
 *
 *   ┌─────────────────────────────────────┐
 *   │ [chip 1 active] [chip 2] [chip 3]   │   SeriesChipRow
 *   │ ┌──────── viewer chrome ─────────┐  │
 *   │ │ ●DefacePill                    │  │
 *   │ │     [active frame img]         │  │
 *   │ └────────────────────────────────┘  │
 *   │  ◀  ━━━━━●━━━━━━━━━  ▶              │
 *   │  27 / 52   keyboard hint            │
 *   └─────────────────────────────────────┘
 *
 * Mobile <1024 px (design-spec K-4 default): chip row + first frame
 * only, slider hidden, mobile-notice line.
 *
 * Reuses the existing JPG fetch route (1-based frameNum on the wire to
 * match the legacy SliceViewer endpoint shape — see deviation in
 * IMPLEMENTATION_DEVIATIONS comment block below).
 *
 * IMPLEMENTATION DEVIATIONS:
 *   - Wire frameNum is 1-based (matches existing /api/studies/[uid]/
 *     series/[N]/frames/[M] route which has Path(..., ge=1)). The
 *     dev-spec §7.2 example URL uses 0-based, but flipping the wire
 *     would break the existing /v1/studies/.../frames endpoint that
 *     buyer-browse-preview already ships. Manifest's frame_count is
 *     the count of frames; UI uses 1..frame_count.
 *   - Keyboard PageUp/Down step is fixed at 10 (design-spec K-1
 *     default).
 */

"use client";

import {
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import clsx from "clsx";
import { getDict, type Locale } from "@/lib/i18n";
import { ModalityFallback } from "@/components/preview/ModalityFallback";

// ---------------------------------------------------------------------------
// Manifest types (mirrors PreviewBatch / PreviewSeriesEntry shape).
// ---------------------------------------------------------------------------

export type PreviewStatus =
  | "generated"
  | "skipped"
  | "quarantined"
  | "pending";

export type DefaceDecision =
  | "required"
  | "not_required"
  | "skipped_unsupported_modality";

/**
 * Subset of phi_scrub_method values the UI can render. Anything else
 * is treated as a generic stone-coloured pill (graceful unknown).
 */
export type DefaceMethod =
  | "afni_refacer_v0_7"
  | "none_required"
  | "modality_no_deface_needed"
  | "deface_failed_input"
  | "deface_failed_runtime"
  | "skipped_burned_in";

export type ManifestSeries = {
  pseudo_series_uid: string;
  series_num: number;
  modality: string;
  body_part?: string | null;
  frame_count: number;
  preview_status: PreviewStatus;
  deface_decision?: DefaceDecision | null;
  deface_method?: DefaceMethod | string | null;
};

export type PreviewManifest = {
  pseudo_study_uid: string;
  pipeline_version: string;
  series: ManifestSeries[];
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PRELOAD_RADIUS = 2; // design-spec §8.1
const PAGE_STEP = 10; // K-1 default
const DRAG_DEBOUNCE_MS = 80; // §8.2
const ANNOUNCE_DEBOUNCE_MS = 200; // §9.2

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export type FrameSliderViewerProps = {
  studyUid: string;
  manifest: PreviewManifest;
  locale?: Locale;
  className?: string;
};

function format(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) =>
    String(vars[k] ?? `{${k}}`),
  );
}

function pickInitialSeries(series: ManifestSeries[]): ManifestSeries | null {
  // Design-spec §3.1: first generated series. Fallback to first
  // entry if every series is non-generated (the caller should have
  // handed off to the all-quarantined fallback in that case, but be
  // defensive).
  const firstGenerated = series.find((s) => s.preview_status === "generated");
  if (firstGenerated) return firstGenerated;
  return series[0] ?? null;
}

export function FrameSliderViewer({
  studyUid,
  manifest,
  locale = "en",
  className,
}: FrameSliderViewerProps) {
  const dict = getDict(locale);
  const t = dict.frameSlider;

  // ----- Series selection ----------------------------------------------------
  const initial = useMemo(() => pickInitialSeries(manifest.series), [manifest.series]);
  const [activeSeriesUid, setActiveSeriesUid] = useState<string | null>(
    initial?.pseudo_series_uid ?? null,
  );
  const activeSeries = useMemo<ManifestSeries | null>(() => {
    if (!activeSeriesUid) return null;
    return (
      manifest.series.find((s) => s.pseudo_series_uid === activeSeriesUid) ??
      null
    );
  }, [manifest.series, activeSeriesUid]);

  // Median frame on series enter.
  const initialFrame = useMemo(() => {
    if (!activeSeries) return 1;
    return Math.max(1, Math.floor(activeSeries.frame_count / 2) + 1);
  }, [activeSeries]);

  const [current, setCurrent] = useState<number>(initialFrame);
  // Debounce drag-induced setCurrent so we don't fire 80 fetches in a flick.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const announceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [announce, setAnnounce] = useState<string>("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Cross-series prefetch cache (design-spec K-2 default: keep across swaps).
  // Key: `${seriesUid}:${frame}`.
  const preloaded = useRef<Map<string, true>>(new Map());

  // Reset frame when series changes.
  useEffect(() => {
    setCurrent(initialFrame);
  }, [initialFrame]);

  // ----- frame URL ----------------------------------------------------------
  const frameUrl = useCallback(
    (seriesNum: number, frame: number) =>
      `/api/studies/${encodeURIComponent(
        studyUid,
      )}/series/${seriesNum}/frames/${frame}`,
    [studyUid],
  );

  // ----- prefetch neighbours -------------------------------------------------
  useEffect(() => {
    if (!activeSeries || activeSeries.preview_status !== "generated") return;
    if (typeof Image === "undefined") return;
    const total = Math.max(1, activeSeries.frame_count);
    const lo = Math.max(1, current - PRELOAD_RADIUS);
    const hi = Math.min(total, current + PRELOAD_RADIUS);
    for (let n = lo; n <= hi; n++) {
      const cacheKey = `${activeSeries.pseudo_series_uid}:${n}`;
      if (preloaded.current.has(cacheKey)) continue;
      const img = new Image();
      img.onload = () => preloaded.current.set(cacheKey, true);
      img.onerror = () => {
        /* tolerate */
      };
      img.src = frameUrl(activeSeries.series_num, n);
    }
  }, [activeSeries, current, frameUrl]);

  // ----- announce frame change to AT (debounced) -----------------------------
  useEffect(() => {
    if (!activeSeries) return;
    if (announceRef.current) clearTimeout(announceRef.current);
    announceRef.current = setTimeout(() => {
      setAnnounce(
        format(t.liveAnnounce, {
          n: current,
          total: activeSeries.frame_count,
          seriesNum: activeSeries.series_num,
        }),
      );
    }, ANNOUNCE_DEBOUNCE_MS);
    return () => {
      if (announceRef.current) clearTimeout(announceRef.current);
    };
  }, [current, activeSeries, t.liveAnnounce]);

  // Cleanup debounce on unmount.
  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (announceRef.current) clearTimeout(announceRef.current);
    },
    [],
  );

  // ----- All-quarantined / all-skipped early-out ----------------------------
  const everySeriesUnavailable = manifest.series.every(
    (s) => s.preview_status !== "generated",
  );
  if (everySeriesUnavailable) {
    const allSkipped = manifest.series.every(
      (s) => s.preview_status === "skipped",
    );
    const allPending = manifest.series.every(
      (s) => s.preview_status === "pending",
    );
    const variant: "unavailable-quarantined" | "unavailable-skipped" | "unavailable-pending" = allPending
      ? "unavailable-pending"
      : allSkipped
        ? "unavailable-skipped"
        : "unavailable-quarantined";
    return <ModalityFallback variant={variant} locale={locale} />;
  }

  // From here on activeSeries is guaranteed non-null because at least
  // one series is generated. Defensive check anyway.
  if (!activeSeries) {
    return <ModalityFallback variant="unavailable-pending" locale={locale} />;
  }

  const total = Math.max(1, activeSeries.frame_count);
  const isMobile =
    typeof window !== "undefined" && window.innerWidth < 1024;

  // ----- Keyboard ------------------------------------------------------------
  function clamp(n: number): number {
    if (n < 1) return 1;
    if (n > total) return total;
    return n;
  }
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    let handled = true;
    switch (e.key) {
      case "ArrowLeft":
      case "ArrowDown":
        setCurrent((c) => clamp(c - 1));
        break;
      case "ArrowRight":
      case "ArrowUp":
        setCurrent((c) => clamp(c + 1));
        break;
      case "PageDown":
        setCurrent((c) => clamp(c - PAGE_STEP));
        break;
      case "PageUp":
        setCurrent((c) => clamp(c + PAGE_STEP));
        break;
      case "Home":
        setCurrent(1);
        break;
      case "End":
        setCurrent(total);
        break;
      default:
        handled = false;
    }
    if (handled) e.preventDefault();
  }

  function onSliderChange(value: number) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(
      () => setCurrent(clamp(value)),
      DRAG_DEBOUNCE_MS,
    );
  }

  function onSelectSeries(seriesUid: string) {
    const next = manifest.series.find((s) => s.pseudo_series_uid === seriesUid);
    if (!next) return;
    if (next.preview_status !== "generated") return;
    setActiveSeriesUid(seriesUid);
    if (containerRef.current) containerRef.current.focus();
  }

  return (
    <section
      ref={containerRef}
      data-testid="frame-slider-viewer"
      role="region"
      aria-label={format(t.regionLabel, {
        n: activeSeries.series_num,
        total: manifest.series.length,
      })}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className={clsx(
        "flex flex-col gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700",
        className,
      )}
    >
      {/* SeriesChipRow */}
      <SeriesChipRow
        series={manifest.series}
        activeSeriesUid={activeSeriesUid}
        onSelect={onSelectSeries}
        locale={locale}
      />

      {/* Viewer chrome */}
      <div
        data-testid="frame-viewer-chrome"
        className="relative w-full overflow-hidden rounded-md"
        style={{ backgroundColor: "#000000", minHeight: 480, maxHeight: 600 }}
      >
        <DefacePill
          method={(activeSeries.deface_method ?? null) as DefaceMethod | null}
          modality={activeSeries.modality}
          locale={locale}
        />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={`${activeSeries.pseudo_series_uid}-${current}`}
          src={frameUrl(activeSeries.series_num, current)}
          alt={format(t.frameAlt, {
            n: current,
            total,
            seriesNum: activeSeries.series_num,
            modality: activeSeries.modality,
          })}
          draggable={false}
          className="mx-auto block max-h-[600px] w-auto select-none"
          style={{ objectFit: "contain", maxWidth: "100%" }}
        />
      </div>

      {/* SR-only live region */}
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {announce}
      </div>

      {/* Slider row + counter (hidden on mobile per K-4 default) */}
      {!isMobile && total > 1 ? (
        <div className="flex flex-col gap-2 px-1">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label={t.previousFrame}
              onClick={() => setCurrent((c) => clamp(c - 1))}
              disabled={current <= 1}
              className="rounded-md border border-border px-2 py-1 text-sm text-text disabled:opacity-40"
            >
              ◀
            </button>
            <input
              type="range"
              data-testid="frame-slider"
              min={1}
              max={total}
              defaultValue={current}
              key={`${activeSeries.pseudo_series_uid}-slider`}
              aria-label={t.sliderLabel}
              aria-valuemin={1}
              aria-valuemax={total}
              aria-valuenow={current}
              aria-valuetext={format(t.frameCounter, {
                n: current,
                total,
              })}
              onChange={(e) => onSliderChange(Number(e.target.value))}
              className="flex-1"
            />
            <button
              type="button"
              aria-label={t.nextFrame}
              onClick={() => setCurrent((c) => clamp(c + 1))}
              disabled={current >= total}
              className="rounded-md border border-border px-2 py-1 text-sm text-text disabled:opacity-40"
            >
              ▶
            </button>
          </div>
          <p
            data-testid="frame-counter"
            className="text-xs font-mono text-text-muted"
          >
            {format(t.frameCounter, { n: current, total })}
          </p>
          <p className="text-[11px] text-text-muted">{t.keyboardHint}</p>
        </div>
      ) : null}

      {isMobile ? (
        <p
          data-testid="frame-slider-mobile-notice"
          className="px-1 text-[11px] text-text-muted"
        >
          {t.mobileNotice}
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// SeriesChipRow
// ---------------------------------------------------------------------------

function SeriesChipRow({
  series,
  activeSeriesUid,
  onSelect,
  locale,
}: {
  series: ManifestSeries[];
  activeSeriesUid: string | null;
  onSelect: (uid: string) => void;
  locale: Locale;
}) {
  const dict = getDict(locale);
  const t = dict.frameSlider;

  function chipLabel(s: ManifestSeries): string {
    const tpl = s.body_part ? t.chipLabel : t.chipNoBodyPart;
    return format(tpl, {
      seriesNum: s.series_num,
      modality: s.modality,
      bodyPart: s.body_part ?? "",
      frameCount: s.frame_count,
    });
  }

  function disabledTooltip(s: ManifestSeries): string {
    if (s.preview_status === "quarantined") return t.chipDisabledTooltip.quarantined;
    if (s.preview_status === "skipped") return t.chipDisabledTooltip.skipped;
    if (s.preview_status === "pending") return t.chipDisabledTooltip.pending;
    return "";
  }

  // Dropdown fallback for ≥6 series (design-spec §6.1).
  if (series.length >= 6) {
    return (
      <div
        role="tablist"
        aria-label={t.seriesSelectorLabel}
        className="px-1 pb-1"
      >
        <select
          data-testid="series-selector"
          value={activeSeriesUid ?? ""}
          onChange={(e) => onSelect(e.target.value)}
          className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          {series.map((s) => (
            <option
              key={s.pseudo_series_uid}
              value={s.pseudo_series_uid}
              disabled={s.preview_status !== "generated"}
            >
              {chipLabel(s)}
              {s.preview_status !== "generated"
                ? ` (${disabledTooltip(s)})`
                : ""}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div
      role="tablist"
      aria-label={t.seriesSelectorLabel}
      className="flex flex-wrap gap-1.5 px-1 pb-1"
    >
      {series.map((s) => {
        const active = s.pseudo_series_uid === activeSeriesUid;
        const isDisabled = s.preview_status !== "generated";
        const labelText = chipLabel(s);
        return (
          <button
            key={s.pseudo_series_uid}
            type="button"
            role="tab"
            data-testid="series-chip"
            data-state={active ? "active" : isDisabled ? "disabled" : "inactive"}
            aria-selected={active}
            aria-disabled={isDisabled || undefined}
            disabled={isDisabled}
            title={isDisabled ? disabledTooltip(s) : undefined}
            onClick={() => !isDisabled && onSelect(s.pseudo_series_uid)}
            className={clsx(
              "inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-xs",
              active
                ? "bg-primary-700 text-white"
                : isDisabled
                  ? "cursor-not-allowed bg-bg-muted text-text-muted"
                  : "bg-bg-muted text-text hover:bg-border/60",
            )}
          >
            {isDisabled ? <span aria-hidden>⚠</span> : null}
            <span>{labelText}</span>
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DefacePill — design-spec §7.1-§7.4
// ---------------------------------------------------------------------------

type PillVariant = "amber" | "stone" | "rose" | "hidden";

function pillVariant(method: DefaceMethod | null, modality: string): {
  variant: PillVariant;
  textKey: keyof Dict["frameSlider"]["defacePill"] | null;
  fillKey?: string;
} {
  if (!method) return { variant: "hidden", textKey: null };
  switch (method) {
    case "afni_refacer_v0_7":
      return { variant: "amber", textKey: "afni" };
    case "modality_no_deface_needed":
      return { variant: "stone", textKey: "noneRequiredModality" };
    case "none_required":
      // body-part anatomy variant — chest CT etc.
      return { variant: "stone", textKey: "noneRequiredAnatomy" };
    case "deface_failed_input":
    case "deface_failed_runtime":
      return { variant: "rose", textKey: "failed" };
    case "skipped_burned_in":
      return { variant: "rose", textKey: "skippedBurnedIn" };
    default:
      void modality;
      return { variant: "hidden", textKey: null };
  }
}

type Dict = ReturnType<typeof getDict>;

export function DefacePill({
  method,
  modality,
  locale = "en",
}: {
  method: DefaceMethod | null;
  modality: string;
  locale?: Locale;
}) {
  const dict = getDict(locale);
  const { variant, textKey } = pillVariant(method, modality);
  if (variant === "hidden" || !textKey) return null;
  const tpl = dict.frameSlider.defacePill[textKey];
  const text = format(tpl, { modality });
  const styles =
    variant === "amber"
      ? {
          backgroundColor: "rgba(245, 158, 11, 0.18)",
          borderColor: "rgba(245, 158, 11, 0.35)",
          color: "#fcd34d",
        }
      : variant === "rose"
        ? {
            backgroundColor: "#fee2e2",
            borderColor: "rgba(185, 28, 28, 0.35)",
            color: "#b91c1c",
          }
        : {
            backgroundColor: "rgba(245, 245, 244, 0.85)",
            borderColor: "rgba(120, 113, 108, 0.4)",
            color: "#44403c",
          };

  return (
    <div
      data-testid="deface-pill"
      data-variant={variant}
      role="status"
      aria-label={text}
      className={clsx(
        "absolute z-10 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
      )}
      style={{
        ...styles,
        top: 12,
        left: 12,
        minWidth: 140,
        transition: "opacity 200ms ease",
      }}
    >
      <span aria-hidden>●</span>
      <span>{text}</span>
    </div>
  );
}
