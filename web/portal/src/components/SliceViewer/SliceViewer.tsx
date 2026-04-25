/**
 * SliceViewer — design-spec §7. Pure React + <img> on top of a black
 * canvas-bg; navigates a pre-rendered JPEG sequence served by the BFF.
 *
 * Allowed (FR-PREVIEW-2):
 *   - slice navigation (slider / ↑↓ / wheel / Page / Home / End)
 *   - zoom (CSS transform: scale, 0.5×–4×, +/- keys)
 *   - pan (mouse drag, cursor: grab/grabbing)
 *   - window-level (CSS filter brightness/contrast 0–200%)
 *
 * Forbidden (SaMD CI lint, NFR-COMPLIANCE):
 *   - measurement / segmentation / annotation / AI overlay / diagnose
 *
 * Lint contract: this folder MUST NOT contain the strings 'measure',
 * 'segment', 'diagnose', 'annotate'. The CI grep is in design-spec §15.
 */

"use client";

import {
  KeyboardEvent,
  MouseEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  WheelEvent,
} from "react";
import clsx from "clsx";
import { getDict, type Locale } from "@/lib/i18n";
import { ModalityFallback } from "@/components/preview/ModalityFallback";

export type SliceViewerProps = {
  studyUid: string;
  /** Number of frames available (preview_slice_count). 1 = single-frame. */
  sliceCount: number;
  /** Series number to render — D-13 MVP fixes this to 1. */
  seriesNum?: number;
  modality?: string | null;
  locale?: Locale;
  className?: string;
  /** Fixed initial frame; defaults to median. */
  initialFrame?: number;
};

type PreloadCache = Map<number, true>;

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 4;
const ZOOM_STEP = 1.25;
const PRELOAD_RADIUS = 3;

function format(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) =>
    String(vars[k] ?? `{${k}}`),
  );
}

export function SliceViewer({
  studyUid,
  sliceCount,
  seriesNum = 1,
  modality,
  locale = "en",
  className,
  initialFrame,
}: SliceViewerProps) {
  const dict = getDict(locale);
  const totalFrames = Math.max(1, sliceCount);
  const median = Math.max(1, Math.floor(totalFrames / 2) + 1);
  const [current, setCurrent] = useState<number>(initialFrame ?? median);
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [bright, setBright] = useState<number>(100);
  const [contrast, setContrast] = useState<number>(100);
  const [imgState, setImgState] = useState<"loading" | "loaded" | "error">(
    "loading",
  );
  const [dragOrigin, setDragOrigin] = useState<{
    x: number;
    y: number;
    panX: number;
    panY: number;
  } | null>(null);
  const preloaded = useRef<PreloadCache>(new Map());
  const containerRef = useRef<HTMLDivElement>(null);

  const frameUrl = useCallback(
    (frame: number) =>
      `/api/studies/${encodeURIComponent(studyUid)}/series/${seriesNum}/frames/${frame}`,
    [studyUid, seriesNum],
  );

  // --- Preload neighbours (NFR-PERF-2) -------------------------------------
  useEffect(() => {
    if (typeof Image === "undefined") return;
    const lo = Math.max(1, current - PRELOAD_RADIUS);
    const hi = Math.min(totalFrames, current + PRELOAD_RADIUS);
    for (let n = lo; n <= hi; n++) {
      if (preloaded.current.has(n)) continue;
      const img = new Image();
      img.onload = () => preloaded.current.set(n, true);
      img.onerror = () => {
        /* tolerate; will retry on demand */
      };
      img.src = frameUrl(n);
    }
  }, [current, totalFrames, frameUrl]);

  // --- Keyboard ------------------------------------------------------------
  function clamp(n: number): number {
    if (n < 1) return 1;
    if (n > totalFrames) return totalFrames;
    return n;
  }
  function clampZoom(n: number): number {
    if (n < ZOOM_MIN) return ZOOM_MIN;
    if (n > ZOOM_MAX) return ZOOM_MAX;
    return n;
  }
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    let handled = true;
    switch (e.key) {
      case "ArrowDown":
        setCurrent((c) => clamp(c - 1));
        break;
      case "ArrowUp":
        setCurrent((c) => clamp(c + 1));
        break;
      case "PageDown":
        setCurrent((c) => clamp(c - 5));
        break;
      case "PageUp":
        setCurrent((c) => clamp(c + 5));
        break;
      case "Home":
        setCurrent(1);
        break;
      case "End":
        setCurrent(totalFrames);
        break;
      case "+":
      case "=":
        setZoom((z) => clampZoom(z * ZOOM_STEP));
        break;
      case "-":
      case "_":
        setZoom((z) => clampZoom(z / ZOOM_STEP));
        break;
      case "0":
        setZoom(1);
        setPan({ x: 0, y: 0 });
        break;
      default:
        handled = false;
    }
    if (handled) e.preventDefault();
  }

  // --- Mouse wheel = slice nav ---------------------------------------------
  function onWheel(e: WheelEvent<HTMLDivElement>) {
    e.preventDefault();
    if (e.deltaY > 0) setCurrent((c) => clamp(c - 1));
    else if (e.deltaY < 0) setCurrent((c) => clamp(c + 1));
  }

  // --- Drag pan ------------------------------------------------------------
  function onMouseDown(e: MouseEvent<HTMLDivElement>) {
    setDragOrigin({ x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y });
  }
  function onMouseMove(e: MouseEvent<HTMLDivElement>) {
    if (!dragOrigin) return;
    setPan({
      x: dragOrigin.panX + (e.clientX - dragOrigin.x),
      y: dragOrigin.panY + (e.clientY - dragOrigin.y),
    });
  }
  function onMouseUp() {
    setDragOrigin(null);
  }

  // --- Reset transient state when frame changes ----------------------------
  useEffect(() => {
    setImgState("loading");
  }, [current, seriesNum]);

  const transform = useMemo(
    () => `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
    [pan.x, pan.y, zoom],
  );
  const filter = useMemo(
    () => `brightness(${bright}%) contrast(${contrast}%)`,
    [bright, contrast],
  );

  // --- Single-frame variant: hide the slider --------------------------------
  const isSingleFrame = totalFrames <= 1;

  return (
    <section
      ref={containerRef}
      data-testid="slice-viewer"
      role="region"
      aria-label="Slice viewer"
      tabIndex={0}
      onKeyDown={onKeyDown}
      onWheel={onWheel}
      className={clsx(
        "flex flex-col gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700",
        className,
      )}
    >
      <div
        className={clsx(
          "relative w-full overflow-hidden rounded-md",
          dragOrigin ? "cursor-grabbing" : "cursor-grab",
        )}
        style={{ backgroundColor: "#000000", minHeight: 480 }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        {imgState === "loading" ? (
          <div
            data-testid="slice-viewer-loading"
            className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-white"
          >
            <span
              aria-hidden
              className="inline-block size-8 animate-spin rounded-full border-2 border-white border-t-transparent"
            />
            <p className="text-sm">
              {format(dict.viewer.loadingFirstSlice, {
                n: current,
                total: totalFrames,
              })}
            </p>
          </div>
        ) : null}
        {imgState === "error" ? (
          <div
            data-testid="slice-viewer-error"
            className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center text-white"
          >
            <span aria-hidden className="text-3xl">⚠</span>
            <h4 className="text-base font-medium">
              {format(dict.viewer.frameFailedShort, { n: current })}
            </h4>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setImgState("loading")}
                className="rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white"
              >
                {dict.viewer.frameFailedRetry}
              </button>
              {!isSingleFrame ? (
                <button
                  type="button"
                  onClick={() => setCurrent((c) => clamp(c + 1))}
                  className="rounded-md border border-white/40 px-3 py-1.5 text-sm font-medium text-white"
                >
                  {dict.viewer.frameFailedSkip}
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={`${seriesNum}-${current}`}
          src={frameUrl(current)}
          alt={`Slice ${current} of ${totalFrames} — ${modality ?? ""}`.trim()}
          draggable={false}
          onLoad={() => setImgState("loaded")}
          onError={() => setImgState("error")}
          style={{
            transform,
            filter,
            transition: "transform 60ms linear, filter 60ms linear",
          }}
          className={clsx(
            "mx-auto block max-h-[600px] w-auto select-none",
            imgState === "loaded" ? "opacity-100" : "opacity-0",
          )}
        />
        {/* Zoom overlay (top-right) */}
        <div
          data-testid="zoom-controls"
          className="absolute right-3 top-3 flex flex-col gap-1 rounded-md bg-black/40 p-1 text-white"
        >
          <button
            type="button"
            aria-label={dict.viewer.zoomIn}
            onClick={() => setZoom((z) => clampZoom(z * ZOOM_STEP))}
            className="size-7 rounded text-base hover:bg-white/10"
          >
            +
          </button>
          <button
            type="button"
            aria-label={dict.viewer.zoomOut}
            onClick={() => setZoom((z) => clampZoom(z / ZOOM_STEP))}
            className="size-7 rounded text-base hover:bg-white/10"
          >
            −
          </button>
          <button
            type="button"
            aria-label={dict.viewer.zoomReset}
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
            className="size-7 rounded text-sm hover:bg-white/10"
          >
            ⟲
          </button>
        </div>
        {/* Window-level overlay (top-left) */}
        <div
          data-testid="window-level-controls"
          className="absolute left-3 top-3 flex flex-col gap-2 rounded-md bg-black/40 p-2 text-white"
        >
          <label className="flex items-center gap-2 text-[11px]">
            <span className="w-12 opacity-80">
              {dict.viewer.brightnessLabel}
            </span>
            <input
              type="range"
              min={0}
              max={200}
              value={bright}
              aria-label={dict.viewer.brightnessLabel}
              onChange={(e) => setBright(Number(e.target.value))}
              className="w-24"
            />
          </label>
          <label className="flex items-center gap-2 text-[11px]">
            <span className="w-12 opacity-80">
              {dict.viewer.contrastLabel}
            </span>
            <input
              type="range"
              min={0}
              max={200}
              value={contrast}
              aria-label={dict.viewer.contrastLabel}
              onChange={(e) => setContrast(Number(e.target.value))}
              className="w-24"
            />
          </label>
        </div>
      </div>

      {/* Slider row + counter + keyboard hint */}
      {!isSingleFrame ? (
        <div className="flex flex-col gap-2 px-1">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label={dict.viewer.previousSlice}
              onClick={() => setCurrent((c) => clamp(c - 1))}
              disabled={current <= 1}
              className="rounded-md border border-border px-2 py-1 text-sm text-text disabled:opacity-40"
            >
              ◀
            </button>
            <input
              type="range"
              data-testid="slice-slider"
              min={1}
              max={totalFrames}
              value={current}
              aria-label={dict.viewer.sliderLabel}
              aria-valuemin={1}
              aria-valuemax={totalFrames}
              aria-valuenow={current}
              aria-valuetext={format(dict.viewer.sliceCounter, {
                n: current,
                total: totalFrames,
              })}
              onChange={(e) => setCurrent(clamp(Number(e.target.value)))}
              className="flex-1"
            />
            <button
              type="button"
              aria-label={dict.viewer.nextSlice}
              onClick={() => setCurrent((c) => clamp(c + 1))}
              disabled={current >= totalFrames}
              className="rounded-md border border-border px-2 py-1 text-sm text-text disabled:opacity-40"
            >
              ▶
            </button>
          </div>
          <p
            data-testid="slice-counter"
            className="text-xs font-mono text-text-muted"
          >
            {format(dict.viewer.sliceCounter, {
              n: current,
              total: totalFrames,
            })}
          </p>
          <p className="text-[11px] text-text-muted">
            {dict.viewer.keyboardHint}
          </p>
        </div>
      ) : (
        <p className="px-1 text-[11px] text-text-muted">
          {dict.viewer.keyboardHintSingleFrame}
        </p>
      )}
    </section>
  );
}

/** Convenience wrapper used by StudyDetailPanel — picks SliceViewer vs
 *  ModalityFallback based on the study's preview_status. */
export function SliceViewerOrFallback({
  studyUid,
  sliceCount,
  previewStatus,
  modality,
  locale,
}: {
  studyUid: string;
  sliceCount: number;
  previewStatus: "verified" | "pending" | "phi_detected" | "not_applicable";
  modality?: string | null;
  locale?: Locale;
}) {
  if (previewStatus === "verified") {
    return (
      <SliceViewer
        studyUid={studyUid}
        sliceCount={sliceCount}
        modality={modality}
        locale={locale}
      />
    );
  }
  const variant =
    previewStatus === "phi_detected"
      ? "unavailable-phi"
      : previewStatus === "not_applicable"
        ? "unavailable-modality"
        : "unavailable-pending";
  return (
    <ModalityFallback
      variant={variant}
      modality={modality}
      locale={locale}
    />
  );
}
