"use client";

/**
 * <ViewerPaneV4> — C-DV-Viewer (design-spec-dicom-viewer §4.1).
 *
 * Layout 5-stack (top → bottom):
 *
 *   1. <SeriesPicker>     — custom dropdown, 1-9 keyboard hotkey
 *   2. <ViewerToolbar>    — zoom/pan/W-L/preset/reset/fullscreen
 *   3. <ViewerCanvas>     — frame img + overlay + watermark
 *   4. Frame slider       — slice ━━━━━●━━━━ N / total
 *   5. <Disclaimer>       — "Display only — not for diagnostic use"
 *
 * Replaces both <ViewerPaneV3> + <FrameSliderViewer>. Reuses the
 * existing JPG fetch route + DefacePill from the v3 module — keeps the
 * v3 surface intact for any other caller of <FrameSliderViewer>.
 *
 * Bidirectional sync with the right-rail SERIES card is implemented in
 * <StudyDetailPanel>: it owns activeSeriesUid + onActiveSeriesChange
 * and forwards them to both this pane and SeriesMiniCardListV4.
 *
 * Keyboard shortcuts (FR-DV-2.4 / FR-DV-3 / FR-DV-4):
 *   Series: 1..9
 *   Zoom:   +/= zoom in, − zoom out
 *   Reset:  R
 *   Fullsc: F
 *   Frame:  ←↓ −1, →↑ +1, PgUp −10, PgDn +10, Home / End
 *
 * Performance: zoom/pan/W-L are CSS transform/filter only (no canvas
 * pixel manipulation). Preload radius 2 — same as v3 FrameSliderViewer
 * (kept verbatim).
 */

import {
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import clsx from "clsx";
import {
  DefacePill,
  type DefaceMethod,
  type ManifestSeries,
  type PreviewManifest,
} from "@/components/preview/FrameSliderViewer";
import { ModalityFallback } from "@/components/preview/ModalityFallback";
import { type Locale } from "@/lib/i18n";
import { SeriesPicker } from "./SeriesPicker";
import { ViewerToolbar } from "./ViewerToolbar";
import {
  PAN_DEFAULT,
  ViewerCanvas,
  WL_DEFAULT,
  WW_DEFAULT,
  ZOOM_DEFAULT,
  clampZoom,
  type Pan,
} from "./ViewerCanvas";
import { PRESETS, type PresetId, type PresetSpec } from "./PresetMenu";

const PRELOAD_RADIUS = 2;
const PAGE_STEP = 10;
const DRAG_DEBOUNCE_MS = 80;
const ANNOUNCE_DEBOUNCE_MS = 200;
const ZOOM_KEY_FACTOR = 1.1;

function pickInitialSeries(series: ManifestSeries[]): ManifestSeries | null {
  return (
    series.find((s) => s.preview_status === "generated") ?? series[0] ?? null
  );
}

function median1Based(total: number): number {
  if (total <= 1) return 1;
  return Math.max(1, Math.floor(total / 2) + 1);
}

function isCt(modality: string | null | undefined): boolean {
  return (modality ?? "").toUpperCase() === "CT";
}

export type ViewerPaneV4Props = {
  studyUid: string;
  manifest: PreviewManifest;
  /** Active series UID — controlled by parent for right-rail sync. */
  activeSeriesUid: string | null;
  /** Notify parent on series change (keyboard / dropdown / right-rail). */
  onActiveSeriesChange: (seriesUid: string) => void;
  /** Optional overlay slots (4 corners). */
  overlayTopLeft?: React.ReactNode | null;
  overlayTopRight?: React.ReactNode | null;
  overlayBottomLeft?: React.ReactNode | null;
  overlayBottomRight?: React.ReactNode | null;
  locale?: Locale;
  className?: string;
};

export function ViewerPaneV4({
  studyUid,
  manifest,
  activeSeriesUid,
  onActiveSeriesChange,
  overlayTopLeft,
  overlayTopRight,
  overlayBottomLeft,
  overlayBottomRight,
  locale = "en",
  className,
}: ViewerPaneV4Props) {
  void locale;
  const router = useRouter();
  const searchParams = useSearchParams();

  // ---------- Series resolution ----------
  const initial = useMemo(
    () => pickInitialSeries(manifest.series),
    [manifest.series],
  );
  const resolvedSeries = useMemo<ManifestSeries | null>(() => {
    if (!activeSeriesUid) return initial;
    const found = manifest.series.find(
      (s) => s.pseudo_series_uid === activeSeriesUid,
    );
    if (found && found.preview_status === "generated") return found;
    if (typeof console !== "undefined" && activeSeriesUid && !found) {
      // FR-DV-2.6 — warn on URL pointing at unknown series_num.
      console.warn(
        `[viewer] series uid "${activeSeriesUid}" not in manifest; falling back`,
      );
    }
    return initial;
  }, [activeSeriesUid, initial, manifest.series]);

  // Initialise from `?series=N` once on mount if parent hasn't picked.
  const initSyncedRef = useRef(false);
  useEffect(() => {
    if (initSyncedRef.current) return;
    initSyncedRef.current = true;
    const seriesParam = searchParams?.get("series");
    if (!seriesParam) return;
    const num = Number(seriesParam);
    if (!Number.isFinite(num)) return;
    const target = manifest.series.find(
      (s) => s.series_num === num && s.preview_status === "generated",
    );
    if (target && target.pseudo_series_uid !== activeSeriesUid) {
      onActiveSeriesChange(target.pseudo_series_uid);
    } else if (!target) {
      // Fallback log per FR-DV-2.6.
      console.warn(
        `[viewer] ?series=${num} not available; falling back to first generated`,
      );
    }
  }, [
    searchParams,
    manifest.series,
    activeSeriesUid,
    onActiveSeriesChange,
  ]);

  // ---------- Frame state ----------
  const initialFrame = useMemo(
    () => median1Based(resolvedSeries?.frame_count ?? 1),
    [resolvedSeries],
  );
  const [current, setCurrent] = useState<number>(initialFrame);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const announceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [announce, setAnnounce] = useState<string>("");
  const containerRef = useRef<HTMLElement>(null);

  // Preload cache.
  const preloaded = useRef<Map<string, true>>(new Map());

  // ---------- Viewer state (zoom/pan/wl + preset + tool) ----------
  const [zoom, setZoom] = useState(ZOOM_DEFAULT);
  const [pan, setPan] = useState<Pan>(PAN_DEFAULT);
  const [ww, setWw] = useState(WW_DEFAULT);
  const [wl, setWl] = useState(WL_DEFAULT);
  const [activePreset, setActivePreset] = useState<PresetId>("none");
  const [activeTool, setActiveTool] = useState<"pan" | "wl">("pan");
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Reset frame index + zoom/pan when series changes; preserve W-L per
  // Q-DV-2 (Kyle implicit accept).
  const lastSeriesUidRef = useRef<string | null>(null);
  useEffect(() => {
    if (!resolvedSeries) return;
    if (lastSeriesUidRef.current === resolvedSeries.pseudo_series_uid) return;
    lastSeriesUidRef.current = resolvedSeries.pseudo_series_uid;
    setCurrent(initialFrame);
    setZoom(ZOOM_DEFAULT);
    setPan(PAN_DEFAULT);
    // ww/wl + activePreset preserved.
  }, [resolvedSeries, initialFrame]);

  // ---------- frame URL + prefetch ----------
  const frameUrl = useCallback(
    (seriesNum: number, frame: number) =>
      `/api/studies/${encodeURIComponent(
        studyUid,
      )}/series/${seriesNum}/frames/${frame}`,
    [studyUid],
  );

  useEffect(() => {
    if (!resolvedSeries) return;
    if (resolvedSeries.preview_status !== "generated") return;
    if (typeof Image === "undefined") return;
    const total = Math.max(1, resolvedSeries.frame_count);
    const lo = Math.max(1, current - PRELOAD_RADIUS);
    const hi = Math.min(total, current + PRELOAD_RADIUS);
    for (let n = lo; n <= hi; n++) {
      const cacheKey = `${resolvedSeries.pseudo_series_uid}:${n}`;
      if (preloaded.current.has(cacheKey)) continue;
      const img = new Image();
      img.onload = () => preloaded.current.set(cacheKey, true);
      img.onerror = () => {
        /* tolerate */
      };
      img.src = frameUrl(resolvedSeries.series_num, n);
    }
    // FR-DV-6.1 — cap LRU at 100 entries.
    if (preloaded.current.size > 100) {
      const keys = Array.from(preloaded.current.keys());
      for (let i = 0; i < keys.length - 100; i++) {
        preloaded.current.delete(keys[i]);
      }
    }
  }, [resolvedSeries, current, frameUrl]);

  // ---------- SR live region (debounced) ----------
  useEffect(() => {
    if (!resolvedSeries) return;
    if (announceRef.current) clearTimeout(announceRef.current);
    announceRef.current = setTimeout(() => {
      setAnnounce(
        `Frame ${current} of ${resolvedSeries.frame_count} — series ${resolvedSeries.series_num}`,
      );
    }, ANNOUNCE_DEBOUNCE_MS);
    return () => {
      if (announceRef.current) clearTimeout(announceRef.current);
    };
  }, [current, resolvedSeries]);

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (announceRef.current) clearTimeout(announceRef.current);
    },
    [],
  );

  // ---------- All-unavailable early-out ----------
  const everyUnavailable = manifest.series.every(
    (s) => s.preview_status !== "generated",
  );
  if (everyUnavailable) {
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

  if (!resolvedSeries) {
    return <ModalityFallback variant="unavailable-pending" locale={locale} />;
  }

  const total = Math.max(1, resolvedSeries.frame_count);
  const isMobile =
    typeof window !== "undefined" && window.innerWidth < 1024;

  // ---------- Helpers ----------
  function clampFrame(n: number): number {
    if (n < 1) return 1;
    if (n > total) return total;
    return n;
  }

  function onSelectSeries(seriesUid: string) {
    const next = manifest.series.find(
      (s) => s.pseudo_series_uid === seriesUid,
    );
    if (!next) return;
    if (next.preview_status !== "generated") return;
    onActiveSeriesChange(seriesUid);
    if (containerRef.current) containerRef.current.focus();
    // URL replace (FR-DV-2.5)
    if (router && searchParams) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("series", String(next.series_num));
      router.replace(`?${params.toString()}`, { scroll: false });
    }
  }

  function applyPreset(p: PresetSpec | "custom") {
    if (p === "custom") {
      setActivePreset("custom");
      return;
    }
    if (p.ww == null || p.wl == null) {
      setActivePreset(p.id);
      return;
    }
    setActivePreset(p.id);
    setWw(p.ww);
    setWl(p.wl);
  }

  function reset() {
    setZoom(ZOOM_DEFAULT);
    setPan(PAN_DEFAULT);
    setWw(WW_DEFAULT);
    setWl(WL_DEFAULT);
    setActivePreset("none");
  }

  function toggleFullscreen() {
    setIsFullscreen((v) => !v);
  }

  // ---------- Keyboard ----------
  function onKeyDown(e: KeyboardEvent<HTMLElement>) {
    const tag =
      typeof document !== "undefined" &&
      document.activeElement &&
      "tagName" in document.activeElement
        ? (document.activeElement as HTMLElement).tagName
        : "";
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    let handled = true;
    switch (e.key) {
      case "ArrowLeft":
      case "ArrowDown":
        setCurrent((c) => clampFrame(c - 1));
        break;
      case "ArrowRight":
      case "ArrowUp":
        setCurrent((c) => clampFrame(c + 1));
        break;
      case "PageUp":
        setCurrent((c) => clampFrame(c - PAGE_STEP));
        break;
      case "PageDown":
        setCurrent((c) => clampFrame(c + PAGE_STEP));
        break;
      case "Home":
        setCurrent(1);
        break;
      case "End":
        setCurrent(total);
        break;
      case "+":
      case "=":
        setZoom((z) => clampZoom(z * ZOOM_KEY_FACTOR));
        break;
      case "-":
      case "_":
        setZoom((z) => clampZoom(z / ZOOM_KEY_FACTOR));
        break;
      case "r":
      case "R":
        reset();
        break;
      case "f":
      case "F":
        toggleFullscreen();
        break;
      case "Escape":
        if (isFullscreen) setIsFullscreen(false);
        else handled = false;
        break;
      default: {
        // Series 1-9 hotkey
        if (/^[1-9]$/.test(e.key)) {
          const idx = Number(e.key) - 1;
          const target = manifest.series[idx];
          if (target && target.preview_status === "generated") {
            onSelectSeries(target.pseudo_series_uid);
          }
        } else {
          handled = false;
        }
      }
    }
    if (handled) e.preventDefault();
  }

  function onSliderChange(value: number) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(
      () => setCurrent(clampFrame(value)),
      DRAG_DEBOUNCE_MS,
    );
  }

  // ---------- Toolbar handlers ----------
  function onZoomIn() {
    setZoom((z) => clampZoom(z * ZOOM_KEY_FACTOR));
  }
  function onZoomOut() {
    setZoom((z) => clampZoom(z / ZOOM_KEY_FACTOR));
  }

  function onCanvasChange(next: {
    zoom: number;
    pan: Pan;
    ww: number;
    wl: number;
  }) {
    setZoom(next.zoom);
    setPan(next.pan);
    if (next.ww !== ww || next.wl !== wl) {
      setWw(next.ww);
      setWl(next.wl);
      setActivePreset(matchPresetByValues(next.ww, next.wl) ?? "custom");
    }
  }

  // ---------- Render ----------
  const presetDisabled = !isCt(resolvedSeries.modality);
  const url = frameUrl(resolvedSeries.series_num, current);
  const alt = `Frame ${current} of ${total} — series ${resolvedSeries.series_num} ${resolvedSeries.modality}`;

  return (
    <section
      ref={containerRef}
      data-testid="dv-viewer-pane"
      role="region"
      aria-label="DICOM viewer"
      aria-busy={false}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className={clsx(
        "rv-viewer-pane-v4 focus-visible:outline-none",
        className,
      )}
    >
      <SeriesPicker
        series={manifest.series}
        activeSeriesUid={resolvedSeries.pseudo_series_uid}
        onSelect={onSelectSeries}
      />

      <ViewerToolbar
        activeTool={activeTool}
        onSelectTool={setActiveTool}
        activePreset={activePreset}
        onSelectPreset={applyPreset}
        presetDisabled={presetDisabled}
        ww={ww}
        wl={wl}
        zoom={zoom}
        onZoomIn={onZoomIn}
        onZoomOut={onZoomOut}
        onReset={reset}
        onToggleFullscreen={toggleFullscreen}
        isFullscreen={isFullscreen}
      />

      <ViewerCanvas
        frameUrl={url}
        alt={alt}
        zoom={zoom}
        pan={pan}
        ww={ww}
        wl={wl}
        modality={resolvedSeries.modality}
        activeTool={activeTool}
        onChange={onCanvasChange}
        defacePill={
          <DefacePill
            method={
              (resolvedSeries.deface_method ?? null) as DefaceMethod | null
            }
            modality={resolvedSeries.modality}
            locale={locale}
          />
        }
        overlay={{
          topLeft: overlayTopLeft,
          topRight: overlayTopRight,
          bottomLeft: overlayBottomLeft,
          bottomRight: overlayBottomRight,
        }}
      />

      {/* SR-only live region — frame announce */}
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {announce}
      </div>

      {/* Slider (hidden on mobile) */}
      {!isMobile && total > 1 ? (
        <div
          className="rv-viewer-slider-v4"
          aria-label="Frame slider"
          data-testid="dv-frame-slider-wrap"
        >
          <span className="rv-viewer-slider-v4__label">slice</span>
          <input
            type="range"
            className="rv-viewer-slider-v4__range"
            min={1}
            max={total}
            value={current}
            key={`${resolvedSeries.pseudo_series_uid}-slider`}
            aria-label="Frame slider"
            aria-valuemin={1}
            aria-valuemax={total}
            aria-valuenow={current}
            data-testid="dv-frame-slider"
            onChange={(e) => onSliderChange(Number(e.target.value))}
          />
          <span
            className="rv-viewer-slider-v4__count"
            data-testid="dv-frame-counter"
          >
            {current} / {total}
          </span>
        </div>
      ) : null}

      {isMobile ? (
        <div
          className="rv-viewer-mobile-notice"
          data-testid="dv-mobile-notice"
        >
          Mobile preview — full interactions available on desktop.
        </div>
      ) : null}

      <div
        className="rv-viewer-disclaimer-v4"
        role="note"
        data-testid="dv-disclaimer"
      >
        Display only — not for diagnostic use (SaMD disclaimer)
      </div>
    </section>
  );
}

/**
 * If (ww, wl) exactly matches one of the built-in presets, return its
 * id. Used to keep the preset menu's ✓ in sync when the user manually
 * lands on a preset value via right-drag.
 */
function matchPresetByValues(ww: number, wl: number): PresetId | null {
  const tol = 0.5;
  for (const p of PRESETS) {
    if (
      p.ww != null &&
      p.wl != null &&
      Math.abs(p.ww - ww) < tol &&
      Math.abs(p.wl - wl) < tol
    ) {
      return p.id;
    }
  }
  return null;
}
